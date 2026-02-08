# page_2.py
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
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


def render():
    st.title("📈 Orders & Revenue Over Time")
    st.caption("Monthly trend using orders + order_items (revenue = sum of item prices)")

    with st.sidebar:
        st.subheader("Page 2 controls")
        gran = st.selectbox("Time granularity", ["Monthly", "Weekly"], index=0)
        show_points = st.checkbox("Show markers", value=True)

    orders = read_csv("olist_orders_dataset.csv")
    items = read_csv("olist_order_items_dataset.csv")

    # Parse timestamps
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )
    items["price"] = pd.to_numeric(items["price"], errors="coerce")

    df = orders.merge(items[["order_id", "price"]], on="order_id", how="left")

    df = df.dropna(subset=["order_purchase_timestamp"])
    df["price"] = df["price"].fillna(0.0)

    if gran == "Monthly":
        df["period"] = df["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
        title = "Monthly Orders Count & Revenue"
    else:
        # Week starts Monday by default; this makes nice regular bins
        df["period"] = df["order_purchase_timestamp"].dt.to_period("W").dt.start_time
        title = "Weekly Orders Count & Revenue"

    agg = (
        df.groupby("period")
        .agg(
            orders=("order_id", "nunique"),
            revenue=("price", "sum"),
        )
        .sort_index()
        .reset_index()
    )

    fig = plt.figure(figsize=(16, 7))
    ax1 = fig.add_subplot(111)

    ax1.set_title(title, fontsize=16, pad=10)
    ax1.plot(
        agg["period"],
        agg["orders"],
        linestyle="-",
        marker="o" if show_points else None,
        linewidth=2,
        label="Orders (unique order_id)",
    )
    ax1.set_xlabel("Period")
    ax1.set_ylabel("Orders")
    ax1.grid(axis="y", linestyle="--", alpha=0.35)

    ax2 = ax1.twinx()
    ax2.plot(
        agg["period"],
        agg["revenue"],
        linestyle="--",
        marker="o" if show_points else None,
        linewidth=2,
        color="green",
        label="Revenue (sum of item price)",
    )
    ax2.set_ylabel("Revenue")

    # Combined legend
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", frameon=True)

    st.pyplot(fig, clear_figure=True)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total orders", f"{int(agg['orders'].sum()):,}")
    with c2:
        st.metric("Total revenue (items price)", f"{float(agg['revenue'].sum()):,.2f}")

    with st.expander("Show aggregated table"):
        st.dataframe(agg, use_container_width=True)
