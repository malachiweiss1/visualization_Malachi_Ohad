from pathlib import Path

import pandas as pd
import pydeck as pdk
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
def load_seller_orders() -> pd.DataFrame:
    items = read_csv("olist_order_items_dataset.csv")[
        ["order_id", "seller_id", "price", "freight_value"]
    ].copy()
    orders = read_csv("olist_orders_dataset.csv")[
        ["order_id", "order_status", "order_purchase_timestamp"]
    ].copy()
    sellers = read_csv("olist_sellers_dataset.csv")[
        ["seller_id", "seller_state", "seller_zip_code_prefix"]
    ].copy()

    items["price"] = pd.to_numeric(items["price"], errors="coerce").fillna(0.0)
    items["freight_value"] = pd.to_numeric(items["freight_value"], errors="coerce").fillna(0.0)
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )

    df = items.merge(orders, on="order_id", how="left")
    df = df.merge(sellers, on="seller_id", how="left")
    df = df.dropna(subset=["order_purchase_timestamp", "seller_state"]).copy()
    df["order_date"] = df["order_purchase_timestamp"].dt.date
    return df


@st.cache_data(show_spinner=True)
def load_state_centroids() -> pd.DataFrame:
    geo = read_csv("olist_geolocation_dataset.csv")[
        ["geolocation_state", "geolocation_lat", "geolocation_lng"]
    ].copy()
    geo["geolocation_lat"] = pd.to_numeric(geo["geolocation_lat"], errors="coerce")
    geo["geolocation_lng"] = pd.to_numeric(geo["geolocation_lng"], errors="coerce")
    geo = geo.dropna(subset=["geolocation_state", "geolocation_lat", "geolocation_lng"])

    centroids = (
        geo.groupby("geolocation_state", as_index=False)
        .agg(
            lat=("geolocation_lat", "mean"),
            lon=("geolocation_lng", "mean"),
        )
        .rename(columns={"geolocation_state": "seller_state"})
    )
    return centroids


def _seller_agg(df: pd.DataFrame) -> pd.DataFrame:
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
    agg["avg_order_value"] = (agg["revenue"] / agg["orders"].replace(0, pd.NA)).fillna(0.0)
    agg["freight_ratio_pct"] = ((agg["freight"] / agg["revenue"].replace(0, pd.NA)) * 100.0).fillna(0.0)
    return agg


def render():
    st.title("🗺️ Top Seller Leaderboard by State")
    st.caption("Map shows the top seller in each state after your filters.")

    df = load_seller_orders()
    df = df[df["order_status"] == "delivered"].copy()
    min_date = df["order_date"].min()
    max_date = df["order_date"].max()

    states = sorted(df["seller_state"].dropna().unique().tolist())

    with st.sidebar:
        st.subheader("Page 5 controls")
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        selected_states = st.multiselect("Seller states", options=states, default=states)
        rank_metric = st.selectbox(
            "Rank top seller by",
            ["revenue", "orders", "avg_order_value", "number_of_sellers"],
            index=0,
        )
        min_orders = st.slider("Minimum orders per seller", min_value=1, max_value=200, value=1, step=1)
        max_state_limit = max(1, len(states))
        max_states = st.slider(
            "Show top N states",
            min_value=1,
            max_value=max_state_limit,
            value=max_state_limit,
            step=1,
        )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    filtered = df[(df["order_date"] >= start_date) & (df["order_date"] <= end_date)].copy()
    if selected_states:
        filtered = filtered[filtered["seller_state"].isin(selected_states)].copy()

    if filtered.empty:
        st.warning("No data after filters.")
        return

    seller_stats = _seller_agg(filtered)
    seller_stats = seller_stats[seller_stats["orders"] >= min_orders].copy()
    if seller_stats.empty:
        st.warning("No sellers match the minimum orders filter.")
        return

    state_seller_counts = (
        seller_stats.groupby("seller_state", as_index=False)
        .agg(number_of_sellers=("seller_id", "nunique"))
    )

    # One top seller per state; when ranking by number_of_sellers, seller selection is by revenue.
    seller_pick_metric = "revenue" if rank_metric == "number_of_sellers" else rank_metric
    top_by_state = (
        seller_stats.sort_values(seller_pick_metric, ascending=False)
        .groupby("seller_state", as_index=False)
        .first()
    )
    top_by_state = top_by_state.merge(state_seller_counts, on="seller_state", how="left")
    top_by_state = top_by_state.sort_values(rank_metric, ascending=False).head(max_states)

    centroids = load_state_centroids()
    map_df = top_by_state.merge(centroids, on="seller_state", how="left")
    map_df = map_df.dropna(subset=["lat", "lon"]).copy()

    if map_df.empty:
        st.warning("Could not map selected states (missing centroid coordinates).")
        return

    metric_max = float(map_df[rank_metric].max()) if len(map_df) else 1.0
    metric_max = metric_max if metric_max > 0 else 1.0
    map_df["radius"] = (map_df[rank_metric] / metric_max) * 45000 + 8000

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[lon, lat]",
        get_radius="radius",
        get_fill_color="[76, 120, 168, 180]",
        get_line_color="[255, 255, 255, 200]",
        line_width_min_pixels=1,
        pickable=True,
        stroked=True,
    )
    text_layer = pdk.Layer(
        "TextLayer",
        data=map_df,
        get_position="[lon, lat]",
        get_text="seller_state",
        get_size=14,
        size_units="pixels",
        get_pixel_offset=[0, 18],
        get_color=[20, 20, 20, 220],
        get_alignment_baseline="'top'",
        get_text_anchor="'middle'",
        pickable=False,
    )

    view_state = pdk.ViewState(latitude=-14.2, longitude=-51.9, zoom=3.4, pitch=0)
    tooltip = {
        "html": (
            "<b>State:</b> {seller_state}<br/>"
            "<b>Seller:</b> {seller_id}<br/>"
            "<b>Orders:</b> {orders}<br/>"
            "<b>Revenue:</b> {revenue}<br/>"
            "<b>Avg Order:</b> {avg_order_value}<br/>"
            "<b>Freight Ratio %:</b> {freight_ratio_pct}"
        )
    }

    st.pydeck_chart(
        pdk.Deck(
            map_provider="carto",
            map_style=pdk.map_styles.LIGHT,
            initial_view_state=view_state,
            layers=[layer, text_layer],
            tooltip=tooltip,
        )
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("States shown", f"{len(map_df):,}")
    with c2:
        st.metric("Top seller metric", rank_metric)
    with c3:
        st.metric("Combined revenue", f"{map_df['revenue'].sum():,.2f}")

    table = map_df[
        [
            "seller_state",
            "seller_id",
            "number_of_sellers",
            "orders",
            "items",
            "revenue",
            "avg_order_value",
            "freight_ratio_pct",
        ]
    ].sort_values(rank_metric, ascending=False)

    st.subheader("Leaderboard Table")
    st.dataframe(table, use_container_width=True)
