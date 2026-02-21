# main.py
import streamlit as st

import page_1
import page_2
import page_3
import page_4
import page_5
import page_6
import page_7

st.set_page_config(
    page_title="Olist Dashboard",
    page_icon="📊",
    layout="wide",
)

PAGES = {
    "Page 1": page_1,
    "Page 2": page_2,
    "Page 3": page_3,
    "Page 4": page_4,
    "Page 5": page_5,
    "Page 6": page_6,
    "Page 7": page_7,
}

with st.sidebar:
    st.title("Navigation")
    choice = st.radio("Go to", list(PAGES.keys()), index=0)

PAGES[choice].render()
