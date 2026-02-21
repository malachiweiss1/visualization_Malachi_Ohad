from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt


def _resolve_data_dir() -> Path:
    local = Path("data")
    return local if local.exists() else Path("/mnt/data")


DATA_DIR = _resolve_data_dir()


@st.cache_data(show_spinner=False)
def read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path.resolve()}")
    return pd.read_csv(path)


def render():
    st.title("📈 Orders & Revenue Over Time")
    st.caption("Interactive small-multiples: brush to zoom, hover for precise values.")

    with st.sidebar:
        st.subheader("Controls")
        gran = st.selectbox("Time granularity", ["Monthly", "Weekly"], index=0)
        show_points = st.checkbox("Show points", value=False)
        smooth = st.checkbox("Rolling average", value=True)
        window = st.slider("Rolling window (periods)", 2, 16, 4, 1) if smooth else 0
        log_revenue = st.checkbox("Log revenue (log1p)", value=False)
        reset_zoom = st.checkbox("Reset zoom", value=False)

    orders = read_csv("olist_orders_dataset.csv")
    items = read_csv("olist_order_items_dataset.csv")

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )
    items["price"] = pd.to_numeric(items["price"], errors="coerce")

    df = orders.merge(items[["order_id", "price"]], on="order_id", how="left")
    df = df.dropna(subset=["order_purchase_timestamp"])
    df["price"] = df["price"].fillna(0.0)

    if gran == "Monthly":
        df["period"] = df["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
        title = "Monthly Trend"
    else:
        df["period"] = df["order_purchase_timestamp"].dt.to_period("W").dt.start_time
        title = "Weekly Trend"

    agg = (
        df.groupby("period")
        .agg(
            orders=("order_id", "nunique"),
            revenue=("price", "sum"),
        )
        .sort_index()
        .reset_index()
    )

    if len(agg) == 0:
        st.info("No data available after cleaning timestamps.")
        return

    if log_revenue:
        agg["revenue_plot"] = np.log1p(agg["revenue"])
        revenue_title = "Revenue (log1p)"
    else:
        agg["revenue_plot"] = agg["revenue"]
        revenue_title = "Revenue"

    if smooth and window and len(agg) >= window:
        agg["orders_smooth"] = agg["orders"].rolling(window).mean()
        agg["revenue_smooth"] = agg["revenue_plot"].rolling(window).mean()
    else:
        agg["orders_smooth"] = np.nan
        agg["revenue_smooth"] = np.nan

    # ---- Summary metrics (context without clutter)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total orders", f"{int(agg['orders'].sum()):,}")
    c2.metric("Total revenue", f"{float(agg['revenue'].sum()):,.2f}")
    c3.metric("Date range", f"{agg['period'].min().date()} → {agg['period'].max().date()}")

    st.divider()
    st.subheader(title)

    # ---- Interactive selections
    hover = alt.selection_point(
        fields=["period"],
        nearest=True,
        on="mouseover",
        empty=False,
        clear="mouseout",
    )

    brush = alt.selection_interval(encodings=["x"])
    if reset_zoom:
        brush = alt.selection_interval(encodings=["x"], empty="all")

    base = alt.Chart(agg).encode(
        x=alt.X("period:T", title=None),
    )

    # Use brush as a filter for the main charts (zoom)
    filtered = base.transform_filter(brush)

    # Tooltip content: always show original revenue (not log) for interpretability
    tooltip = [
        alt.Tooltip("period:T", title="Period"),
        alt.Tooltip("orders:Q", title="Orders", format=","),
        alt.Tooltip("revenue:Q", title="Revenue", format=",.2f"),
    ]

    line_kwargs = {"strokeWidth": 2}

    # ---- Orders chart
    orders_line = filtered.mark_line(**line_kwargs).encode(
        y=alt.Y("orders:Q", title="Orders", axis=alt.Axis(grid=True)),
        tooltip=tooltip,
    )

    orders_smooth = filtered.mark_line(opacity=0.5, strokeDash=[4, 3]).encode(
        y=alt.Y("orders_smooth:Q", title=None),
    )

    orders_points = filtered.mark_circle(size=35).encode(
        y="orders:Q",
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.0)),
        tooltip=tooltip,
    ).add_params(hover)

    orders_rule = filtered.mark_rule(opacity=0.25).encode(
        x="period:T"
    ).transform_filter(hover)

    orders_layer = orders_line
    if smooth and window:
        orders_layer = orders_layer + orders_smooth
    if show_points:
        orders_layer = orders_layer + orders_points + orders_rule

    orders_chart = orders_layer.properties(height=260)

    # ---- Revenue chart
    revenue_line = filtered.mark_line(**line_kwargs).encode(
        y=alt.Y("revenue_plot:Q", title=revenue_title, axis=alt.Axis(grid=True)),
        tooltip=tooltip,
    )

    revenue_smooth = filtered.mark_line(opacity=0.5, strokeDash=[4, 3]).encode(
        y=alt.Y("revenue_smooth:Q", title=None),
    )

    revenue_points = filtered.mark_circle(size=35).encode(
        y="revenue_plot:Q",
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.0)),
        tooltip=tooltip,
    ).add_params(hover)

    revenue_rule = filtered.mark_rule(opacity=0.25).encode(
        x="period:T"
    ).transform_filter(hover)

    revenue_layer = revenue_line
    if smooth and window:
        revenue_layer = revenue_layer + revenue_smooth
    if show_points:
        revenue_layer = revenue_layer + revenue_points + revenue_rule

    revenue_chart = revenue_layer.properties(height=260)

    # ---- Overview brush (mini timeline)
    overview = (
        base.mark_area(opacity=0.25)
        .encode(
            y=alt.Y("orders:Q", title=None, axis=alt.Axis(labels=False, ticks=False, grid=False)),
        )
        .properties(height=70)
        .add_params(brush)
    )

    final = alt.vconcat(
        orders_chart,
        revenue_chart,
        overview,
        spacing=18,
    ).resolve_scale(x="shared")

    st.altair_chart(final, use_container_width=True)

    with st.expander("Show aggregated table"):
        st.dataframe(agg, use_container_width=True)