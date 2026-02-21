from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd
import streamlit as st


def _resolve_data_dir() -> Path:
    local = Path("data")
    if local.exists():
        return local
    return Path("/mnt/data")


DATA_DIR = _resolve_data_dir()


@st.cache_data(show_spinner=False)
def read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path.resolve()}")
    return pd.read_csv(path)


@st.cache_data(show_spinner=True)
def load_category_sales_base() -> pd.DataFrame:
    items = read_csv("olist_order_items_dataset.csv")[["order_id", "product_id", "price"]].copy()
    orders = read_csv("olist_orders_dataset.csv")[
        ["order_id", "order_purchase_timestamp", "order_status"]
    ].copy()
    products = read_csv("olist_products_dataset.csv")[["product_id", "product_category_name"]].copy()

    translation_path = DATA_DIR / "product_category_name_translation.csv"
    if translation_path.exists():
        trans = pd.read_csv(translation_path)
        products = products.merge(trans, on="product_category_name", how="left")
        category_col = "product_category_name_english"
    else:
        category_col = "product_category_name"

    products[category_col] = products[category_col].fillna("unknown")
    items["price"] = pd.to_numeric(items["price"], errors="coerce").fillna(0.0)
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )

    df = items.merge(orders, on="order_id", how="left")
    df = df.merge(products[["product_id", category_col]], on="product_id", how="left")
    df = df.dropna(subset=["order_purchase_timestamp"]).copy()
    df[category_col] = df[category_col].fillna("unknown")
    df["order_date"] = df["order_purchase_timestamp"].dt.date
    return df.rename(columns={category_col: "category"})


def _window_aggregate(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    scoped = df[
        (df["order_purchase_timestamp"] >= start)
        & (df["order_purchase_timestamp"] <= end)
        & (df["order_status"] == "delivered")
    ].copy()

    agg = (
        scoped.groupby("category", as_index=False)
        .agg(
            revenue=("price", "sum"),
            orders=("order_id", "nunique"),
            items=("order_id", "count"),
            avg_item_price=("price", "mean"),
        )
        .sort_values("revenue", ascending=False)
    )
    return agg


def render():
    st.title("🚀 Top Categories Momentum Matrix")
    st.caption(
        "Bubble chart for top-selling categories. X = revenue growth vs previous period, "
        "Y = revenue in selected date range, bubble size = orders, color = average item price."
    )
    st.info(
        "Read this chart left-to-right: categories on the right are growing vs the previous period. "
        "Higher bubbles generate more revenue, bigger bubbles have more orders."
    )

    df = load_category_sales_base()
    min_ts = df["order_purchase_timestamp"].min().normalize()
    max_ts = df["order_purchase_timestamp"].max().normalize()
    default_start = max(min_ts, (max_ts - pd.DateOffset(months=3)).normalize())

    with st.sidebar:
        st.subheader("Page 7 controls")
        top_n = st.slider("Top categories", 5, 30, 15, 1)
        date_range = st.date_input(
            "Selected date range",
            value=(default_start.date(), max_ts.date()),
            min_value=min_ts.date(),
            max_value=max_ts.date(),
        )
        min_orders = st.slider("Minimum orders in selected range", 1, 200, 10, 1)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        selected_start_date, selected_end_date = date_range
    else:
        selected_start_date, selected_end_date = default_start.date(), max_ts.date()

    current_start = pd.Timestamp(selected_start_date).normalize()
    current_end_day = pd.Timestamp(selected_end_date).normalize()
    current_end = current_end_day + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    window_days = int((current_end_day - current_start).days) + 1

    if window_days <= 0:
        st.warning("Invalid date range. Please select an end date after the start date.")
        return

    previous_end_day = current_start - pd.Timedelta(days=1)
    previous_start_day = previous_end_day - pd.Timedelta(days=window_days - 1)
    previous_start = previous_start_day.normalize()
    previous_end = previous_end_day + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    if previous_start < min_ts:
        st.warning("Not enough historical data for comparison. Move the date range forward.")
        return

    current_agg = _window_aggregate(df, current_start, current_end)
    previous_agg = _window_aggregate(df, previous_start, previous_end).rename(
        columns={
            "revenue": "prev_revenue",
            "orders": "prev_orders",
            "items": "prev_items",
            "avg_item_price": "prev_avg_item_price",
        }
    )

    if current_agg.empty:
        st.warning("No delivered-order data in the selected range.")
        return

    top_categories = current_agg["category"].head(top_n).tolist()
    plot_df = current_agg[current_agg["category"].isin(top_categories)].copy()
    plot_df = plot_df[plot_df["orders"] >= min_orders].copy()
    if plot_df.empty:
        st.warning("No categories left after the minimum orders filter.")
        return

    plot_df = plot_df.merge(previous_agg, on="category", how="left")
    plot_df["prev_revenue"] = plot_df["prev_revenue"].fillna(0.0)
    plot_df["growth_pct"] = (
        (plot_df["revenue"] - plot_df["prev_revenue"]) / plot_df["prev_revenue"].replace(0, pd.NA)
    ) * 100.0
    plot_df["growth_defined"] = plot_df["prev_revenue"] > 0

    chart_df = plot_df[plot_df["growth_defined"]].copy()
    if chart_df.empty:
        st.warning("No categories have previous-period revenue, so growth cannot be computed.")
        return

    size_min, size_max = 70.0, 900.0
    orders_norm = chart_df["orders"].astype(float)
    if orders_norm.max() > orders_norm.min():
        marker_sizes = size_min + (
            (orders_norm - orders_norm.min()) / (orders_norm.max() - orders_norm.min())
        ) * (size_max - size_min)
    else:
        marker_sizes = pd.Series([250.0] * len(chart_df), index=chart_df.index)

    fig, ax = plt.subplots(figsize=(13, 7))
    scatter = ax.scatter(
        chart_df["growth_pct"],
        chart_df["revenue"],
        s=marker_sizes,
        c=chart_df["avg_item_price"],
        cmap="plasma",
        alpha=0.82,
        edgecolors="white",
        linewidths=0.8,
    )
    ax.axvline(0.0, color="#444444", linestyle="--", linewidth=1.2, alpha=0.75)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.set_xlabel("Revenue Growth vs Previous Period (%)")
    ax.set_ylabel("Selected-Range Revenue")
    ax.set_title("Category Momentum Matrix")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))

    cbar = fig.colorbar(scatter, ax=ax, pad=0.01)
    cbar.set_label("Average Item Price")

    for row in chart_df.itertuples(index=False):
        label = row.category if len(row.category) <= 18 else f"{row.category[:17]}…"
        ax.annotate(
            label,
            (row.growth_pct, row.revenue),
            textcoords="offset points",
            xytext=(0, 11),
            ha="center",
            va="bottom",
            fontsize=7,
        )

    plt.tight_layout()
    st.pyplot(fig, clear_figure=True)

    st.caption(
        f"Selected range: {current_start.date()} to {current_end_day.date()} | "
        f"Compared against: {previous_start.date()} to {previous_end_day.date()} "
        "(same number of days, immediately before selected range)."
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Categories shown", f"{len(chart_df):,}")
    with c2:
        st.metric("Selected-range revenue", f"{chart_df['revenue'].sum():,.2f}")
    with c3:
        growth_median = chart_df["growth_pct"].median()
        st.metric("Median growth", f"{growth_median:.1f}%")
    with c4:
        rising_share = (chart_df["growth_pct"] > 0).mean() * 100.0
        st.metric("Categories growing", f"{rising_share:.1f}%")

    excluded_no_prev = int((~plot_df["growth_defined"]).sum())
    if excluded_no_prev > 0:
        st.caption(
            f"{excluded_no_prev} category(ies) were excluded from the chart because "
            "they have no revenue in the previous window."
        )

    table = plot_df[
        ["category", "revenue", "prev_revenue", "growth_pct", "orders", "items", "avg_item_price"]
    ].copy()
    table = table.sort_values("revenue", ascending=False)

    st.subheader("Category Comparison Table")
    st.dataframe(table, use_container_width=True)
