# page_3.py
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


def _split_evenly(total: int, count: int) -> list[int]:
    base = total // count
    remainder = total % count
    return [base + 1] * remainder + [base] * (count - remainder)


def _build_base_df() -> pd.DataFrame:
    data = {
        "quarter": [
            "2017 Q1",
            "2017 Q2",
            "2017 Q3",
            "2017 Q4",
            "2018 Q1",
            "2018 Q2",
            "2018 Q3",
        ],
        "on_time_orders": [4731, 8553, 11727, 15537, 17619, 18643, 11571],
        "late_orders": [531, 796, 915, 2311, 3589, 1338, 1249],
    }
    df = pd.DataFrame(data)
    # Parse quarter labels into timestamp for filtering and grouping.
    # Some pandas versions fail on "YYYY Qn", so normalize to "YYYYQn".
    quarter_norm = df["quarter"].str.replace(" ", "", regex=False)
    df["period_start"] = pd.PeriodIndex(quarter_norm, freq="Q").start_time
    df["period_end"] = pd.PeriodIndex(quarter_norm, freq="Q").end_time.normalize()
    return df


def _build_daily_df(base_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, int | pd.Timestamp]] = []
    for row in base_df.itertuples(index=False):
        days = pd.date_range(row.period_start, row.period_end, freq="D")
        on_time_parts = _split_evenly(int(row.on_time_orders), len(days))
        late_parts = _split_evenly(int(row.late_orders), len(days))

        for d, on_t, late in zip(days, on_time_parts, late_parts):
            records.append(
                {
                    "date": d,
                    "on_time_orders": on_t,
                    "late_orders": late,
                }
            )
    return pd.DataFrame.from_records(records)


def _label_from_period(period: pd.Period, granularity: str) -> str:
    if granularity == "Quarterly":
        p = str(period)
        return p.replace("Q", " Q")
    return str(period)


def _aggregate(df: pd.DataFrame, granularity: str) -> pd.DataFrame:
    rule_map = {
        "Monthly": "M",
        "Quarterly": "Q",
        "Yearly": "Y",
    }
    rule = rule_map[granularity]
    grouped = (
        df.groupby(df["date"].dt.to_period(rule))
        .agg(
            on_time_orders=("on_time_orders", "sum"),
            late_orders=("late_orders", "sum"),
        )
        .sort_index()
        .reset_index(names="period")
    )
    grouped["total_orders"] = grouped["on_time_orders"] + grouped["late_orders"]
    grouped["late_percentage"] = (
        grouped["late_orders"] / grouped["total_orders"] * 100.0
    )
    grouped["label"] = grouped["period"].apply(lambda p: _label_from_period(p, granularity))
    return grouped


def render():
    st.title("🚚 Delivery Performance (Interactive)")
    st.caption(
        "Stacked bars: On Time + Late Orders | Line: Late Percentage | "
        "Date range and granularity are interactive."
    )

    base_df = _build_base_df()
    df = _build_daily_df(base_df)

    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    with st.sidebar:
        st.subheader("Page 3 controls")
        granularity = st.selectbox(
            "Granularity",
            ["Monthly", "Quarterly", "Yearly"],
            index=1,
        )
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    filtered = df[
        (df["date"].dt.date >= start_date)
        & (df["date"].dt.date <= end_date)
    ].copy()

    if filtered.empty:
        st.warning("No data in the selected date range.")
        return

    agg = _aggregate(filtered, granularity)

    fig, ax1 = plt.subplots(figsize=(16, 8))
    x_positions = range(len(agg))
    bar_width = 0.6
    show_data_labels = len(agg) <= 40

    rects1 = ax1.bar(
        x_positions,
        agg["on_time_orders"],
        bar_width,
        label="On Time Orders",
        color="#4C78A8",
    )
    rects2 = ax1.bar(
        x_positions,
        agg["late_orders"],
        bar_width,
        label="Late Orders",
        color="#F58518",
        bottom=agg["on_time_orders"],
    )

    if show_data_labels:
        for rect in rects1:
            h = rect.get_height()
            if h > 0:
                ax1.text(
                    rect.get_x() + rect.get_width() / 2,
                    rect.get_y() + h / 2,
                    f"{int(h)}",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=11,
                )

        for rect in rects2:
            h = rect.get_height()
            if h > 0:
                ax1.text(
                    rect.get_x() + rect.get_width() / 2,
                    rect.get_y() + h / 2,
                    f"{int(h)}",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=11,
                )

        for i, total_orders in enumerate(agg["total_orders"]):
            ax1.text(
                i,
                total_orders,
                f"{int(total_orders)}",
                ha="center",
                va="bottom",
                fontsize=11,
                color="black",
            )

    ax2 = ax1.twinx()
    line_plot, = ax2.plot(
        x_positions,
        agg["late_percentage"],
        color="#2F4B7C",
        linestyle="--",
        marker="o",
        label="Late Percentage",
        linewidth=3,
        markersize=9,
    )

    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0f}%"))

    if show_data_labels:
        for i, percentage in enumerate(agg["late_percentage"]):
            ax2.text(
                i,
                percentage,
                f"{percentage:.1f}%",
                ha="center",
                va="bottom",
                fontsize=11,
                color="#2F4B7C",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7),
            )

    ax1.set_title("Delivery Performance: Volume vs. Late Ratio", fontsize=17)
    ax1.set_xlabel("Period", fontsize=12)
    tick_step = max(1, len(agg) // 20)
    tick_idx = list(range(0, len(agg), tick_step))
    ax1.set_xticks(tick_idx)
    ax1.set_xticklabels(agg["label"].iloc[tick_idx], rotation=45, ha="right", fontsize=10)
    ax1.set_ylabel("Number of Orders", color="black", fontsize=12)
    ax2.set_ylabel("Late Percentage", color="#2F4B7C", fontsize=12)

    min_perc = agg["late_percentage"].min()
    max_perc = agg["late_percentage"].max()
    if min_perc == max_perc:
        ax2.set_ylim(bottom=max(0.0, min_perc - 1.0), top=max_perc + 1.0)
    else:
        ax2.set_ylim(bottom=max(0.0, min_perc * 0.8), top=max_perc * 1.5)

    handles1, labels1 = ax1.get_legend_handles_labels()
    _, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(handles1 + [line_plot], labels1 + labels2, loc="upper left", fontsize=10)

    ax1.grid(True, linestyle="--", alpha=0.7)
    ax2.grid(False)
    plt.tight_layout()

    st.pyplot(fig, clear_figure=True)
    if not show_data_labels:
        st.caption("Point labels are hidden automatically for dense views (more than 40 periods).")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("On Time Orders", f"{int(agg['on_time_orders'].sum()):,}")
    with c2:
        st.metric("Late Orders", f"{int(agg['late_orders'].sum()):,}")
    with c3:
        total = float(agg["total_orders"].sum())
        late = float(agg["late_orders"].sum())
        st.metric("Late Percentage", f"{(late / total * 100.0) if total else 0.0:.2f}%")

    with st.expander("Show aggregated table"):
        st.dataframe(
            agg[
                ["label", "on_time_orders", "late_orders", "total_orders", "late_percentage"]
            ].rename(columns={"label": "period"}),
            use_container_width=True,
        )
