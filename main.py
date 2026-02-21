import streamlit as st

import page_1
import page_2
import page_3
import page_4
import page_5
import page_6
import page_7

from ui import inject_global_css

st.set_page_config(
    page_title="Olist — Academic Visualization Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()

PAGES = {
    "01 — Categories & Revenue Concentration": page_1,
    "02 — Orders & Revenue Over Time": page_2,
    "03 — Page 3": page_3,
    "04 — Page 4": page_4,
    "05 — Page 5": page_5,
    "06 — Page 6": page_6,
    "07 — Page 7": page_7,
}

with st.sidebar:
    st.title("Olist Dashboard")
    st.caption("Academic visualization showcase")
    choice = st.radio("Navigate", list(PAGES.keys()), index=0)
    st.divider()
    st.caption("Tip: Hover charts, box-select, and zoom.")

PAGES[choice].render()