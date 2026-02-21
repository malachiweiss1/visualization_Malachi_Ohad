# page_4.py
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


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
def load_base() -> pd.DataFrame:
    orders = read_csv("olist_orders_dataset.csv")[
        [
            "order_id",
            "order_status",
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]
    ].copy()
    items = read_csv("olist_order_items_dataset.csv")[["order_id", "price"]].copy()

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )
    orders["order_delivered_customer_date"] = pd.to_datetime(
        orders["order_delivered_customer_date"], errors="coerce"
    )
    orders["order_estimated_delivery_date"] = pd.to_datetime(
        orders["order_estimated_delivery_date"], errors="coerce"
    )

    items["price"] = pd.to_numeric(items["price"], errors="coerce").fillna(0.0)
    revenue = items.groupby("order_id", as_index=False)["price"].sum()
    revenue = revenue.rename(columns={"price": "order_value"})

    df = orders.merge(revenue, on="order_id", how="left")
    df["order_value"] = df["order_value"].fillna(0.0)
    df = df.dropna(subset=["order_purchase_timestamp"]).copy()

    df["order_date"] = df["order_purchase_timestamp"].dt.date
    df["hour"] = df["order_purchase_timestamp"].dt.hour
    df["weekday"] = df["order_purchase_timestamp"].dt.day_name()
    df["weekday"] = pd.Categorical(df["weekday"], categories=WEEKDAY_ORDER, ordered=True)

    known_late = (
        df["order_delivered_customer_date"].notna()
        & df["order_estimated_delivery_date"].notna()
    )
    df["late_known"] = known_late
    df["late_flag"] = (
        df["order_delivered_customer_date"] > df["order_estimated_delivery_date"]
    ).astype(float)

    return df


@st.cache_data(show_spinner=False)
def load_seller_orders() -> pd.DataFrame:
    items = read_csv("olist_order_items_dataset.csv")[
        ["order_id", "seller_id", "price", "freight_value"]
    ].copy()
    orders = read_csv("olist_orders_dataset.csv")[
        ["order_id", "order_status", "order_purchase_timestamp"]
    ].copy()
    sellers = read_csv("olist_sellers_dataset.csv")[["seller_id", "seller_state"]].copy()

    items["price"] = pd.to_numeric(items["price"], errors="coerce").fillna(0.0)
    items["freight_value"] = pd.to_numeric(items["freight_value"], errors="coerce").fillna(0.0)
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )

    df = items.merge(orders, on="order_id", how="left")
    df = df.merge(sellers, on="seller_id", how="left")
    df = df.dropna(subset=["order_purchase_timestamp"]).copy()
    df["order_date"] = df["order_purchase_timestamp"].dt.date
    return df


def _build_heatmap(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    if metric == "Order Count":
        table = df.pivot_table(
            index="weekday",
            columns="hour",
            values="order_id",
            aggfunc="count",
            fill_value=0.0,
        )
    elif metric == "Revenue":
        table = df.pivot_table(
            index="weekday",
            columns="hour",
            values="order_value",
            aggfunc="sum",
            fill_value=0.0,
        )
    elif metric == "Average Order Value":
        table = df.pivot_table(
            index="weekday",
            columns="hour",
            values="order_value",
            aggfunc="mean",
            fill_value=0.0,
        )
    else:
        table = df.pivot_table(
            index="weekday",
            columns="hour",
            values="order_id",
            aggfunc="count",
            fill_value=0.0,
        )

    table = table.reindex(index=WEEKDAY_ORDER, columns=list(range(24)), fill_value=0.0)
    return table


def _aggregate_sellers(df: pd.DataFrame) -> pd.DataFrame:
    agg = (
        df.groupby(["seller_id", "seller_state"], as_index=False)
        .agg(
            orders=("order_id", "nunique"),
            items=("order_id", "count"),
            revenue=("price", "sum"),
            freight=("freight_value", "sum"),
        )
        .sort_values("revenue", ascending=False)
    )
    agg["avg_order_value"] = agg["revenue"] / agg["orders"].replace(0, pd.NA)
    agg["avg_order_value"] = agg["avg_order_value"].fillna(0.0)
    agg["freight_ratio_pct"] = (agg["freight"] / agg["revenue"].replace(0, pd.NA)) * 100.0
    agg["freight_ratio_pct"] = agg["freight_ratio_pct"].fillna(0.0)
    return agg


def render():
    st.title("🔥 Time Heatmap: When Orders Happen")
    st.caption(
        "Interactive weekday-by-hour heatmap for delivered orders activity and value."
    )

    df = load_base()
    df = df[df["order_status"] == "delivered"].copy()
    min_date = df["order_date"].min()
    max_date = df["order_date"].max()

    with st.sidebar:
        st.subheader("Page 4 controls")
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        metric = st.selectbox(
            "Heatmap metric",
            ["Order Count", "Revenue", "Average Order Value"],
            index=0,
        )
        cmap = st.selectbox("Color palette", ["YlOrRd", "viridis", "magma", "cividis"], index=0)
        annotate = st.checkbox("Show values in cells", value=False)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    filtered = df[
        (df["order_date"] >= start_date) & (df["order_date"] <= end_date)
    ].copy()

    if filtered.empty:
        st.warning("No data available for current filters.")
        return

    heat = _build_heatmap(filtered, metric)

    fig, ax = plt.subplots(figsize=(16, 6.5))
    im = ax.imshow(heat.values, aspect="auto", cmap=cmap, interpolation="nearest")

    ax.set_title(f"{metric} by Weekday and Hour", fontsize=16, pad=12)
    ax.set_xlabel("Hour of Day", fontsize=11)
    ax.set_ylabel("Weekday", fontsize=11)
    ax.set_xticks(range(24))
    ax.set_xticklabels([str(h) for h in range(24)], fontsize=9)
    ax.set_yticks(range(len(WEEKDAY_ORDER)))
    ax.set_yticklabels(WEEKDAY_ORDER, fontsize=10)

    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label(metric, rotation=90)

    if annotate:
        max_val = float(heat.values.max()) if heat.size else 0.0
        threshold = max_val * 0.55
        for y in range(heat.shape[0]):
            for x in range(heat.shape[1]):
                val = float(heat.iat[y, x])
                txt = f"{val:.0f}" if metric in ("Order Count", "Revenue") else f"{val:.1f}"
                color = "white" if val >= threshold else "black"
                ax.text(x, y, txt, ha="center", va="center", fontsize=7, color=color)

    plt.tight_layout()
    st.pyplot(fig, clear_figure=True)

    stack = heat.stack()
    top_idx = stack.idxmax()
    top_val = float(stack.max())

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Rows included", f"{len(filtered):,}")
    with c2:
        st.metric("Busiest slot", f"{top_idx[0]} @ {top_idx[1]:02d}:00")
    with c3:
        st.metric("Peak value", f"{top_val:,.2f}")

    with st.expander("Show heatmap data table"):
        st.dataframe(heat, use_container_width=True)

    st.divider()
    st.subheader("Seller Landscape")
    st.caption(
        "Each point is a seller. Right/up means more orders/revenue, and bigger circles indicate higher average order value."
    )

    seller_orders = load_seller_orders()
    seller_orders = seller_orders[
        (seller_orders["order_status"] == "delivered")
        & (seller_orders["order_date"] >= start_date)
        & (seller_orders["order_date"] <= end_date)
    ].copy()

    if seller_orders.empty:
        st.warning("No seller rows available for the selected date range.")
        return

    states = sorted(seller_orders["seller_state"].dropna().unique().tolist())
    c1, c2, c3 = st.columns(3)
    with c1:
        state_filter = st.multiselect("Seller state", options=states, default=states[:6])
    with c2:
        top_n = st.slider("Top sellers to display", min_value=20, max_value=300, value=120, step=20)
    with c3:
        label_top_k = st.slider("Label top sellers", min_value=0, max_value=15, value=6, step=1)

    if state_filter:
        seller_orders = seller_orders[seller_orders["seller_state"].isin(state_filter)].copy()

    seller_stats = _aggregate_sellers(seller_orders).head(top_n)
    if seller_stats.empty:
        st.warning("No sellers match current filters.")
        return

    fig2, ax = plt.subplots(figsize=(12, 7))
    size = seller_stats["avg_order_value"].clip(lower=1.0) * 2.2
    sc = ax.scatter(
        seller_stats["orders"],
        seller_stats["revenue"],
        s=size,
        c=seller_stats["freight_ratio_pct"],
        cmap="plasma",
        alpha=0.7,
        edgecolors="white",
        linewidth=0.6,
    )
    ax.set_title("Sellers: Revenue vs Number of Orders", fontsize=14, pad=10)
    ax.set_xlabel("Number of Orders")
    ax.set_ylabel("Revenue")
    ax.grid(True, linestyle="--", alpha=0.25)
    cbar = fig2.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Freight / Revenue (%)", rotation=90)

    if label_top_k > 0:
        for _, row in seller_stats.nlargest(label_top_k, "revenue").iterrows():
            ax.annotate(
                row["seller_id"][:8],
                (row["orders"], row["revenue"]),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=8,
            )

    plt.tight_layout()
    st.pyplot(fig2, clear_figure=True)

    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("Sellers shown", f"{len(seller_stats):,}")
    with c5:
        st.metric("Total seller revenue", f"{seller_stats['revenue'].sum():,.2f}")
    with c6:
        st.metric("Avg freight ratio", f"{seller_stats['freight_ratio_pct'].mean():.2f}%")

    with st.expander("Show seller table"):
        st.dataframe(
            seller_stats[
                [
                    "seller_id",
                    "seller_state",
                    "orders",
                    "items",
                    "revenue",
                    "avg_order_value",
                    "freight_ratio_pct",
                ]
            ],
            use_container_width=True,
        )
