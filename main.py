# main.py
import streamlit as st

import page_1
import page_2
import page_3
import page_4
import page_5
import page_6

st.set_page_config(
    page_title="Olist Dashboard",
    page_icon="📊",
    layout="wide",
)

PAGES = {
    "Page 1 — Top Categories (Revenue + Avg Price + Pie)": page_1,
    "Page 2 — Orders & Revenue Over Time": page_2,
    "Page 3 (empty)": page_3,
    "Page 4 (empty)": page_4,
    "Page 5 (empty)": page_5,
    "Page 6 (empty)": page_6,
}

with st.sidebar:
    st.title("Navigation")
    choice = st.radio("Go to", list(PAGES.keys()), index=0)

PAGES[choice].render()
