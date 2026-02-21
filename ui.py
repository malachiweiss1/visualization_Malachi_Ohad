import streamlit as st

def inject_global_css():
    st.markdown(
        """
        <style>
        /* Reduce top padding, make layout feel tighter */
        .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

        /* Sidebar spacing */
        section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }

        /* Metric cards look cleaner */
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid rgba(17,24,39,0.08);
            padding: 12px 14px;
            border-radius: 14px;
        }

        /* Expander style */
        details {
            border-radius: 14px !important;
            border: 1px solid rgba(17,24,39,0.08) !important;
            background: white;
            padding: 6px 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )