# page_1.py
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st


def _resolve_data_dir() -> Path:
    """
    Prefer local project folder ./data (as user requested).
    Fallback to /mnt/data (useful in notebooks / this sandbox).
    """
    local = Path("data")
    if local.exists():
        return local
    fallback = Path("/mnt/data")
    return fallback


DATA_DIR = _resolve_data_dir()


@st.cache_data(show_spinner=False)
def read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path.resolve()}")
    return pd.read_csv(path)


def render():
    st.title("📦 Top Product Categories — Revenue & Avg Price")
    st.caption("Bars: revenue (sum of item price) | Line: average item price | Bar labels: % of total revenue")

    with st.sidebar:
        st.subheader("Page 1 controls")
        top_n = st.slider("Top N categories", min_value=5, max_value=30, value=12, step=1)

    items = read_csv("olist_order_items_dataset.csv")
    products = read_csv("olist_products_dataset.csv")

    # Optional translation
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

    total_revenue_all = df["price"].dropna().sum()

    stats = (
        df.dropna(subset=["price"])
        .groupby(cat_col)
        .agg(revenue=("price", "sum"), avg_price=("price", "mean"))
        .sort_values("revenue", ascending=False)
        .head(top_n)
    )

    top_revenue = float(stats["revenue"].sum()) if not stats.empty else 0.0
    rest_revenue = max(float(total_revenue_all) - top_revenue, 0.0)
    top_share_of_total = (top_revenue / float(total_revenue_all) * 100.0) if total_revenue_all else 0.0

    if total_revenue_all:
        stats["revenue_pct_of_total"] = stats["revenue"] / float(total_revenue_all) * 100.0
    else:
        stats["revenue_pct_of_total"] = 0.0

    # ---- Figure Layout: Left bar+line, Right pie
    fig = plt.figure(figsize=(18, 9))
    gs = fig.add_gridspec(nrows=1, ncols=2, width_ratios=[3.4, 1.4], wspace=0.25)

    ax1 = fig.add_subplot(gs[0, 0])
    ax_pie = fig.add_subplot(gs[0, 1])

    # Left: bars
    bars = ax1.bar(
        stats.index.astype(str),
        stats["revenue"],
        alpha=0.88,
        label="Revenue (sum of item price)",
    )
    ax1.set_title(
        f"Top Product Categories — Revenue & Avg Price\n(Bar labels = % of TOTAL revenue)",
        fontsize=16,
        pad=14,
    )
    ax1.set_xlabel("Product Category", fontsize=12)
    ax1.set_ylabel("Revenue", fontsize=12)
    ax1.tick_params(axis="x", rotation=35)
    ax1.grid(axis="y", linestyle="--", alpha=0.35)

    for bar, pct in zip(bars, stats["revenue_pct_of_total"].tolist()):
        ax1.annotate(
            f"{pct:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            alpha=0.95,
        )

    # Secondary axis: avg price line
    ax2 = ax1.twinx()
    ax2.plot(
        stats.index.astype(str),
        stats["avg_price"],
        marker="o",
        linestyle="--",
        linewidth=2,
        color="green",
        label="Average Item Price",
    )
    ax2.set_ylabel("Average Item Price", fontsize=12)

    # Legend: move outside so it doesn't cover right ticks
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    leg = ax1.legend(
        h1 + h2,
        l1 + l2,
        loc="upper left",
        bbox_to_anchor=(1.18, 1.00),
        borderaxespad=0.0,
        frameon=True,
        title="Info",
    )
    leg.get_title().set_fontsize(11)

    # Right: pie topN vs rest
    ax_pie.set_title("Share of Total Revenue", fontsize=13, pad=10)
    pie_vals = [top_revenue, rest_revenue]
    pie_labels = [f"Top {top_n}", "All other categories"]

    ax_pie.pie(
        pie_vals,
        labels=pie_labels,
        autopct=lambda p: f"{p:.1f}%",
        startangle=90,
        pctdistance=0.75,
        labeldistance=1.08,
        textprops={"fontsize": 10},
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    ax_pie.axis("equal")

    # Summary panel
    def fmt_money(x: float) -> str:
        return f"{x:,.2f}"

    summary_lines = [
        f"Top-{top_n} revenue:  {fmt_money(top_revenue)}",
        f"Total revenue:       {fmt_money(float(total_revenue_all))}",
        f"Top-{top_n} share:     {top_share_of_total:.1f}%",
    ]
    fig.text(
        0.02,
        0.98,
        "\n".join(summary_lines),
        ha="left",
        va="top",
        fontsize=12,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#F6F6F6", edgecolor="#D0D0D0"),
    )

    st.pyplot(fig, clear_figure=True)

    with st.expander("Show aggregated table (Top categories)"):
        st.dataframe(stats.reset_index().rename(columns={cat_col: "category"}), use_container_width=True)
