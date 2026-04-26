import sys, os
sys.path.insert(0, ".")
import pandas as pd
import streamlit as st
from app.db import get_enriched, get_watchlist_enriched, remove_from_watchlist

st.set_page_config(page_title="Smart Money Screener", layout="wide")

# UI Styling
ACCENT = "#0969da"
st.markdown(f"""<style> @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&display=swap');
    html, body, [class*="st-"] {{ font-family: 'IBM Plex Mono', monospace; }} </style>""", unsafe_allow_html=True)

st.title("📡 Smart Money Screener")

def show_narrative(df):
    if not df.empty and 'sector' in df.columns:
        st.subheader("🌊 Market Narrative")
        heat = df.groupby('sector').size().reset_index(name='Count').sort_values('Count', ascending=False)
        c1, c2 = st.columns([1, 2])
        with c1: st.dataframe(heat, hide_index=True)
        with c2: st.bar_chart(data=heat, x='sector', y='Count', color=ACCENT)

tabs = st.tabs(["🚀 Candidates", "⭐ Watchlist"])

with tabs[0]:
    data = get_enriched()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        show_narrative(df)

with tabs[1]:
    wl = get_watchlist_enriched()
    if wl:
        st.dataframe(pd.DataFrame(wl), use_container_width=True)
