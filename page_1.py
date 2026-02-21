from pathlib import Path

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


def _format_money(x: float) -> str:
    return f"{x:,.2f}"


def render():
    st.title("📦 Product Categories — Revenue, Pricing, and Concentration")
    st.caption("Interactive category-level analysis (revenue = sum of item prices).")

    with st.sidebar:
        st.subheader("Controls")
        top_n = st.slider("Top N categories", 5, 40, 12, 1)
        sort_by = st.selectbox("Sort categories by", ["Revenue", "Average price"], index=0)
        trim_outliers = st.checkbox("Trim extreme prices (1%–99%)", value=True)
        show_table = st.checkbox("Show aggregated table", value=False)

    items = read_csv("olist_order_items_dataset.csv")
    products = read_csv("olist_products_dataset.csv")

    translation_path = DATA_DIR / "product_category_name_translation.csv"
    if translation_path.exists():
        trans = pd.read_csv(translation_path)
        products = products.merge(trans, on="product_category_name", how="left")
        cat_col = "product_category_name_english"
    else:
        cat_col = "product_category_name"

    products[cat_col] = products[cat_col].fillna("unknown")
    items["price"] = pd.to_numeric(items["price"], errors="coerce")

    df = items.merge(products[["product_id", cat_col]], on="product_id", how="left")
    df[cat_col] = df[cat_col].fillna("unknown")
    df = df.dropna(subset=["price"])

    total_revenue_all = float(df["price"].sum()) if len(df) else 0.0

    if trim_outliers and len(df):
        lo, hi = df["price"].quantile([0.01, 0.99]).tolist()
        df = df[(df["price"] >= lo) & (df["price"] <= hi)]

    stats = (
        df.groupby(cat_col)
        .agg(
            revenue=("price", "sum"),
            avg_price=("price", "mean"),
            items=("price", "size"),
        )
        .reset_index()
    )

    if sort_by == "Revenue":
        stats = stats.sort_values("revenue", ascending=False)
    else:
        stats = stats.sort_values("avg_price", ascending=False)

    stats_top = stats.head(top_n).copy()
    stats_top["revenue_pct_of_total"] = (
        (stats_top["revenue"] / total_revenue_all * 100.0) if total_revenue_all else 0.0
    )

    top_revenue = float(stats_top["revenue"].sum()) if len(stats_top) else 0.0
    rest_revenue = max(total_revenue_all - top_revenue, 0.0)
    top_share = (top_revenue / total_revenue_all * 100.0) if total_revenue_all else 0.0

    # ---- Metrics row (academic-style summary)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total revenue", _format_money(total_revenue_all))
    c2.metric(f"Top-{top_n} revenue", _format_money(top_revenue))
    c3.metric(f"Top-{top_n} share", f"{top_share:.1f}%")
    c4.metric("Categories (unique)", f"{stats[cat_col].nunique():,}")

    st.divider()

    # ---- Left: interactive bar chart for revenue
    base = alt.Chart(stats_top).encode(
        x=alt.X(f"{cat_col}:N", sort="-y", title="Category"),
        tooltip=[
            alt.Tooltip(f"{cat_col}:N", title="Category"),
            alt.Tooltip("revenue:Q", title="Revenue", format=",.2f"),
            alt.Tooltip("avg_price:Q", title="Avg price", format=",.2f"),
            alt.Tooltip("items:Q", title="Items", format=","),
            alt.Tooltip("revenue_pct_of_total:Q", title="% of total", format=".1f"),
        ],
    )

    bar = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        y=alt.Y("revenue:Q", title="Revenue"),
    )

    label = base.mark_text(align="center", dy=-8, fontSize=11).encode(
        y=alt.Y("revenue:Q"),
        text=alt.Text("revenue_pct_of_total:Q", format=".1f"),
    )

    revenue_chart = (bar + label).properties(height=420).interactive()

    # ---- Right: concentration chart (Top-N vs Rest)
    share_df = pd.DataFrame(
        {
            "group": [f"Top {top_n}", "All other categories"],
            "revenue": [top_revenue, rest_revenue],
        }
    )

    share_chart = (
        alt.Chart(share_df)
        .mark_bar(cornerRadius=10)
        .encode(
            y=alt.Y("group:N", title=None, sort=["All other categories", f"Top {top_n}"]),
            x=alt.X("revenue:Q", title="Revenue"),
            tooltip=[
                alt.Tooltip("group:N", title="Group"),
                alt.Tooltip("revenue:Q", title="Revenue", format=",.2f"),
            ],
        )
        .properties(height=180)
    )

    # ---- Layout
    left, right = st.columns([3.2, 1.3], vertical_alignment="top")
    with left:
        st.subheader("Top categories (interactive)")
        st.altair_chart(revenue_chart, use_container_width=True)

    with right:
        st.subheader("Concentration")
        st.altair_chart(share_chart, use_container_width=True)

        st.caption("Interpretation: revenue concentration shows whether a few categories dominate sales.")

        # Download aggregated top table
        csv_bytes = stats_top.rename(columns={cat_col: "category"}).to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Top-N aggregation (CSV)",
            data=csv_bytes,
            file_name=f"page1_top_{top_n}_categories.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if show_table:
        with st.expander("Aggregated table (Top categories)", expanded=True):
            out = stats_top.rename(columns={cat_col: "category"}).copy()
            out["revenue_pct_of_total"] = out["revenue_pct_of_total"].round(2)
            st.dataframe(out, use_container_width=True)