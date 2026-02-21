from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
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
def load_seller_revenue_base() -> pd.DataFrame:
    items = read_csv("olist_order_items_dataset.csv")[["order_id", "seller_id", "price"]].copy()
    orders = read_csv("olist_orders_dataset.csv")[
        ["order_id", "order_purchase_timestamp", "order_status"]
    ].copy()

    items["price"] = pd.to_numeric(items["price"], errors="coerce").fillna(0.0)
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )

    df = items.merge(orders, on="order_id", how="left")
    df = df.dropna(subset=["order_purchase_timestamp", "seller_id"]).copy()
    df["order_date"] = df["order_purchase_timestamp"].dt.date
    return df


def _period_rule(granularity: str) -> str:
    return {
        "Weekly": "W",
        "Monthly": "M",
        "Quarterly": "Q",
        "Yearly": "Y",
    }[granularity]


def _format_period_label(ts: pd.Timestamp, granularity: str) -> str:
    if granularity == "Weekly":
        return ts.strftime("%Y-%m-%d")
    if granularity == "Monthly":
        return ts.strftime("%Y-%m")
    if granularity == "Quarterly":
        return f"{ts.year} Q{((ts.month - 1) // 3) + 1}"
    return str(ts.year)


def _aggregate_period(df: pd.DataFrame, granularity: str) -> pd.DataFrame:
    rule = _period_rule(granularity)
    period = df["order_purchase_timestamp"].dt.to_period(rule).rename("period")
    agg = (
        df.groupby(period)
        .agg(
            active_sellers=("seller_id", "nunique"),
            revenue=("price", "sum"),
            orders=("order_id", "nunique"),
            items=("order_id", "count"),
        )
        .reset_index()
        .sort_values("period")
    )
    agg["period_start"] = agg["period"].dt.start_time
    agg["label"] = agg["period_start"].apply(lambda d: _format_period_label(d, granularity))
    agg["revenue_per_seller"] = agg["revenue"] / agg["active_sellers"].replace(0, pd.NA)
    agg["revenue_per_seller"] = agg["revenue_per_seller"].fillna(0.0)
    return agg


def render():
    st.title("🎯 Seller Count vs Revenue Correlation")
    st.caption(
        "Each point is a time period. X = active sellers, Y = company revenue. "
        "Only delivered orders are included."
    )

    df = load_seller_revenue_base()
    min_date = df["order_date"].min()
    max_date = df["order_date"].max()

    with st.sidebar:
        st.subheader("Page 6 controls")
        granularity = st.selectbox(
            "Granularity",
            ["Weekly", "Monthly", "Quarterly", "Yearly"],
            index=0,
        )
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        min_active_sellers = st.slider("Minimum active sellers per period", 1, 700, 1, 1)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    filtered = df[
        (df["order_date"] >= start_date)
        & (df["order_date"] <= end_date)
        & (df["order_status"] == "delivered")
    ].copy()

    if filtered.empty:
        st.warning("No data after filters.")
        return

    agg = _aggregate_period(filtered, granularity)
    agg = agg[agg["active_sellers"] >= min_active_sellers].copy()
    if agg.empty:
        st.warning("No periods remain after the minimum seller threshold.")
        return

    x = agg["active_sellers"].astype(float)
    y = agg["revenue"].astype(float)
    corr = x.corr(y)

    size_min, size_max = 40.0, 420.0
    orders_norm = agg["orders"].astype(float)
    if orders_norm.max() > orders_norm.min():
        marker_sizes = size_min + ((orders_norm - orders_norm.min()) / (orders_norm.max() - orders_norm.min())) * (size_max - size_min)
    else:
        marker_sizes = pd.Series([160.0] * len(agg), index=agg.index)

    fig, ax = plt.subplots(figsize=(13, 7))
    scatter = ax.scatter(
        agg["active_sellers"],
        agg["revenue"],
        s=marker_sizes,
        c=agg["orders"],
        cmap="viridis",
        alpha=0.78,
        edgecolors="white",
        linewidths=0.7,
    )
    cbar = fig.colorbar(scatter, ax=ax, pad=0.01)
    cbar.set_label("Orders in period")

    if len(agg) >= 2 and agg["active_sellers"].nunique() > 1:
        m, b = np.polyfit(agg["active_sellers"], agg["revenue"], 1)
        xs = np.linspace(float(agg["active_sellers"].min()), float(agg["active_sellers"].max()), 100)
        ys = m * xs + b
        ax.plot(xs, ys, color="#E45756", linewidth=2.2, linestyle="--", label="Trend line")

    ax.set_title(f"Correlation by {granularity} Period")
    ax.set_xlabel("Active Sellers (unique seller_id)")
    ax.set_ylabel("Revenue (sum of item price)")
    ax.grid(True, linestyle="--", alpha=0.35)
    if len(agg) >= 2:
        ax.legend(loc="upper left")
    plt.tight_layout()
    st.pyplot(fig, clear_figure=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Periods", f"{len(agg):,}")
    with c2:
        st.metric("Pearson correlation", f"{0.0 if pd.isna(corr) else corr:.3f}")
    with c3:
        st.metric("Total revenue", f"{agg['revenue'].sum():,.2f}")
    with c4:
        st.metric("Avg revenue per seller", f"{agg['revenue_per_seller'].mean():,.2f}")

    st.subheader("Aggregated Period Table")
    st.dataframe(
        agg[
            [
                "label",
                "active_sellers",
                "orders",
                "items",
                "revenue",
                "revenue_per_seller",
            ]
        ].rename(columns={"label": "period"}),
        use_container_width=True,
    )
