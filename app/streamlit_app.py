"""
Streamlit UI — read-only, citeste exclusiv din Supabase.
Nu face niciun API call extern.

Deploy: Streamlit Community Cloud -> conecteaza repo GitHub
Entry point: app/streamlit_app.py
"""
import sys
import os
sys.path.insert(0, ".")

import streamlit as st
import pandas as pd
from datetime import date

from app.db import (
    get_enriched,
    get_scan_results,
    get_watchlist,
    get_watchlist_enriched,
    add_to_watchlist,
    remove_from_watchlist,
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Smart Money Screener",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Smart Money Screener")
    st.caption(f"Data: {date.today().strftime('%d %b %Y')}")
    st.divider()

    page = st.radio(
        "Navigare",
        ["Scanner", "Watchlist"],
        label_visibility="collapsed"
    )

    st.divider()
    st.caption("Date actualizate de 2x/zi via GitHub Actions")
    st.caption("08:00 ET — scan  |  16:30 ET — enrich")

# ─── HELPER ──────────────────────────────────────────────────────────────────

def score_color(score: int) -> str:
    if score >= 70:
        return "🟢"
    elif score >= 45:
        return "🟡"
    else:
        return "🔴"


def fmt_value(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.0f}"
    return str(v)


def fmt_money(v) -> str:
    if not v:
        return "—"
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"


# ─── PAGE: SCANNER ───────────────────────────────────────────────────────────

if page == "Scanner":
    st.header("Scanner — candidati smart money")

    col1, col2, col3 = st.columns(3)
    with col1:
        min_score = st.slider("Score minim", 0, 100, 30, 5)
    with col2:
        days_back = st.selectbox("Perioada", [1, 2, 3, 5], index=0,
                                  format_func=lambda x: f"Ultimele {x} zile")
    with col3:
        st.write("")
        refresh = st.button("Refresh")

    data = get_enriched(days_back=days_back, min_score=min_score)

    if not data:
        st.info("Niciun candidat gasit. Datele se actualizeaza la 08:45 ET si 16:30 ET.")
        st.stop()

    st.caption(f"{len(data)} tickers afisate")

    for row in data:
        ticker = row["ticker"]
        score = row.get("score", 0)
        col_ticker, col_score, col_vol, col_insider, col_si, col_pe, col_btn = st.columns(
            [1.5, 1, 1.5, 2, 1.5, 1.2, 1.2]
        )

        with col_ticker:
            st.markdown(f"**{ticker}**")
            st.caption(row.get("enrich_date", ""))

        with col_score:
            st.markdown(f"{score_color(score)} **{score}**/100")

        with col_vol:
            vol_ratio = row.get("vol_ratio", 0)
            st.metric("Vol ratio", f"{vol_ratio}x" if vol_ratio else "—")

        with col_insider:
            buys = row.get("insider_buys_90d", 0) or 0
            val = fmt_money(row.get("insider_buy_value", 0))
            st.metric("Insider buys", f"{buys} tranz.", delta=val if buys > 0 else None)

        with col_si:
            si = row.get("short_interest_pct")
            st.metric("Short int.", f"{si:.1f}%" if si else "—")

        with col_pe:
            pe = row.get("pe_ratio")
            st.metric("P/E", f"{pe:.1f}" if pe else "—")

        with col_btn:
            st.write("")
            if st.button("+ Watch", key=f"add_{ticker}"):
                add_to_watchlist(ticker)
                st.success(f"{ticker} adaugat!")
                st.rerun()

        st.divider()


# ─── PAGE: WATCHLIST ─────────────────────────────────────────────────────────

elif page == "Watchlist":
    st.header("Watchlist")

    col_add, _ = st.columns([2, 5])
    with col_add:
        with st.form("add_ticker_form", clear_on_submit=True):
            new_ticker = st.text_input("Adauga ticker manual", placeholder="ex: AAPL")
            notes = st.text_input("Note (optional)")
            submitted = st.form_submit_button("Adauga")
            if submitted and new_ticker:
                add_to_watchlist(new_ticker.upper().strip(), notes)
                st.success(f"{new_ticker.upper()} adaugat in watchlist!")
                st.rerun()

    st.divider()

    watchlist_data = get_watchlist_enriched()
    watchlist_raw = get_watchlist()

    if not watchlist_raw:
        st.info("Watchlist gol. Adauga tickers din Scanner sau manual.")
        st.stop()

    # Tickers care nu au inca date enrich
    enriched_tickers = {w["ticker"] for w in watchlist_data}
    all_tickers = {w["ticker"] for w in watchlist_raw}
    missing_enrich = all_tickers - enriched_tickers

    if missing_enrich:
        st.warning(f"Fara date enrich inca: {', '.join(sorted(missing_enrich))} — asteapta urmatorul run")

    for row in watchlist_data:
        ticker = row["ticker"]
        score = row.get("score", 0)

        col_ticker, col_score, col_vol, col_insider, col_date, col_btn = st.columns(
            [1.5, 1, 1.5, 2.5, 1.5, 1.2]
        )

        with col_ticker:
            st.markdown(f"**{ticker}**")

        with col_score:
            st.markdown(f"{score_color(score)} **{score}**/100")

        with col_vol:
            vol_ratio = row.get("vol_ratio", 0)
            st.metric("Vol ratio", f"{vol_ratio}x" if vol_ratio else "—")

        with col_insider:
            buys = row.get("insider_buys_90d", 0) or 0
            val = fmt_money(row.get("insider_buy_value", 0))
            sells = row.get("insider_sells_90d", 0) or 0
            label = f"{buys} buy / {sells} sell"
            st.metric("Insider 90d", label, delta=val if buys > 0 else None)

        with col_date:
            st.caption(f"Ultima actualizare:")
            st.caption(row.get("enrich_date", "—"))

        with col_btn:
            st.write("")
            if st.button("Sterge", key=f"rm_{ticker}"):
                remove_from_watchlist(ticker)
                st.rerun()

        st.divider()
