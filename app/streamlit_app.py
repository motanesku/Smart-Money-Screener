"""
Streamlit UI — read-only, citește exclusiv din Supabase.
Nu face niciun API call extern.
"""
import sys
sys.path.insert(0, ".")

import streamlit as st
from datetime import date

from app.db import (
    get_enriched, get_scan_results,
    get_watchlist, get_watchlist_enriched,
    add_to_watchlist, remove_from_watchlist,
)

st.set_page_config(
    page_title="Smart Money Screener",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── HELPERS ──────────────────────────────────────────────────────────────────

def score_badge(score):
    if score >= 70:
        return f"🟢 {score}/100"
    elif score >= 45:
        return f"🟡 {score}/100"
    return f"🔴 {score}/100"



def fmt_money(v):
    if v is None or v == 0:
        return "—"
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"



def fmt_pct(v):
    if v is None:
        return "—"
    if v < 1:
        return f"{v*100:.1f}%"
    return f"{v:.1f}%"



def show_db_error(e: Exception):
    st.error(f"Eroare conexiune Supabase: {e}")
    st.info("Verifică în Streamlit Cloud > Settings > Secrets: SUPABASE_URL și SUPABASE_KEY.")
    st.stop()


# ── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Smart Money Screener")
    st.caption(f"Data: {date.today().strftime('%d %b %Y')}")
    st.divider()
    page = st.radio("Navigare", ["Scanner", "Watchlist"], label_visibility="collapsed")
    st.divider()
    st.caption("Actualizat 2x/zi via GitHub Actions")
    st.caption("08:45 ET — enrich dimineața")
    st.caption("16:30 ET — enrich după închidere")


# ── PAGE: SCANNER ─────────────────────────────────────────────────────────────

if page == "Scanner":
    st.header("Scanner — candidați smart money")

    c1, c2 = st.columns(2)
    with c1:
        min_score = st.slider("Score minim", 0, 100, 30, 5)
    with c2:
        days_back = st.selectbox("Perioada", [1, 2, 3, 5], format_func=lambda x: f"Ultimele {x} zile")

    try:
        data = get_enriched(days_back=days_back, min_score=min_score)
    except Exception as e:
        show_db_error(e)

    if not data:
        st.info("Niciun candidat. Datele vin la 08:45 ET și 16:30 ET.")
        st.stop()

    st.caption(f"{len(data)} tickers")

    for row in data:
        ticker = row["ticker"]
        score = row.get("score", 0)

        cols = st.columns([1.5, 1.2, 1.5, 2, 1.5, 1.2, 1.2])

        with cols[0]:
            st.markdown(f"**{ticker}**")
            st.caption(row.get("enrich_date", ""))
        with cols[1]:
            st.markdown(score_badge(score))
        with cols[2]:
            vr = row.get("vol_ratio") or 0
            st.metric("Vol ratio", f"{vr}x" if vr else "—")
        with cols[3]:
            buys = row.get("insider_buys_90d") or 0
            val = fmt_money(row.get("insider_buy_value"))
            st.metric("Insider buys 90d", f"{buys} filing", delta=val if buys else None)
        with cols[4]:
            st.metric("Short int.", fmt_pct(row.get("short_interest_pct")))
        with cols[5]:
            pe = row.get("pe_ratio")
            st.metric("P/E", f"{pe:.1f}" if pe is not None else "—")
        with cols[6]:
            st.write("")
            if st.button("+ Watch", key=f"add_{ticker}"):
                try:
                    add_to_watchlist(ticker)
                except Exception as e:
                    show_db_error(e)
                st.success(f"{ticker} adăugat!")
                st.rerun()

        st.divider()


# ── PAGE: WATCHLIST ───────────────────────────────────────────────────────────

elif page == "Watchlist":
    st.header("Watchlist")

    with st.form("add_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 3, 1])
        with c1:
            new_ticker = st.text_input("Ticker", placeholder="ex: NVDA")
        with c2:
            notes = st.text_input("Note (opțional)")
        with c3:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("Adaugă")
        if submitted and new_ticker:
            try:
                add_to_watchlist(new_ticker.upper().strip(), notes)
            except Exception as e:
                show_db_error(e)
            st.success(f"{new_ticker.upper()} adăugat!")
            st.rerun()

    st.divider()

    try:
        wl_raw = get_watchlist()
        wl_data = get_watchlist_enriched()
    except Exception as e:
        show_db_error(e)

    if not wl_raw:
        st.info("Watchlist gol. Adaugă din Scanner sau manual.")
        st.stop()

    enriched_tickers = {w["ticker"] for w in wl_data}
    missing = {w["ticker"] for w in wl_raw} - enriched_tickers
    if missing:
        st.warning(f"Fără date încă: {', '.join(sorted(missing))}")

    for row in wl_data:
        ticker = row["ticker"]
        score = row.get("score", 0)

        cols = st.columns([1.5, 1.2, 1.5, 2.5, 2, 1.2])

        with cols[0]:
            st.markdown(f"**{ticker}**")
        with cols[1]:
            st.markdown(score_badge(score))
        with cols[2]:
            vr = row.get("vol_ratio") or 0
            st.metric("Vol ratio", f"{vr}x" if vr else "—")
        with cols[3]:
            buys = row.get("insider_buys_90d") or 0
            sells = row.get("insider_sells_90d") or 0
            val = fmt_money(row.get("insider_buy_value"))
            st.metric("Insider 90d", f"{buys} buy / {sells} sell", delta=val if buys else None)
        with cols[4]:
            st.caption("Ultima actualizare:")
            st.caption(row.get("enrich_date", "—"))
        with cols[5]:
            st.write("")
            if st.button("Șterge", key=f"rm_{ticker}"):
                try:
                    remove_from_watchlist(ticker)
                except Exception as e:
                    show_db_error(e)
                st.rerun()

        st.divider()
