# components/cards.py
import streamlit as st

def render_cards(kpi_dict: dict, cols=5):
    keys = list(kpi_dict.keys())
    cols = min(cols, len(keys))
    grid = st.columns(cols)
    for i,(k,v) in enumerate(kpi_dict.items()):
        with grid[i % cols]:
            st.metric(label=k, value=v)
