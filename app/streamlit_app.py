"""
Premium Streamlit UI — varianta stabilă fără componente fragile.
Păstrează structura proiectului și backend-ul Supabase.
"""
import sys
sys.path.insert(0, ".")

from datetime import date
import pandas as pd
import streamlit as st

from app.db import (
    get_enriched,
    get_watchlist,
    get_watchlist_enriched,
    get_ticker_history,
    add_to_watchlist,
    remove_from_watchlist,
)

st.set_page_config(page_title="Smart Money Screener", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 1.5rem; max-width: 1500px;}
[data-testid="stMetric"] {background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 14px 16px;}
.hero {padding: 18px 20px; border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; background: linear-gradient(135deg, rgba(36,36,52,0.95), rgba(20,20,30,0.95)); margin-bottom: 14px;}
.hero-title {font-size: 1.55rem; font-weight: 700; margin-bottom: 4px;}
.hero-sub {color: #9aa4b2; font-size: 0.92rem;}
.section-title {font-size: 1.08rem; font-weight: 700; margin: 8px 0 10px 0;}
.small-muted {color: #9aa4b2; font-size: 0.84rem;}
.card {border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 14px 16px; background: rgba(255,255,255,0.02); margin-bottom: 12px;}
</style>
""", unsafe_allow_html=True)


def fmt_money(v):
    if v is None or v == 0:
        return "—"
    try:
        v = float(v)
    except Exception:
        return "—"
    if abs(v) >= 1_000_000_000:
        return f"${v/1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"


def fmt_int(v):
    if v is None or v == 0:
        return "—"
    try:
        return f"{int(v):,}"
    except Exception:
        return "—"


def fmt_pct(v):
    if v is None:
        return "—"
    try:
        v = float(v)
    except Exception:
        return "—"
    if 0 < abs(v) < 1:
        return f"{v*100:.1f}%"
    return f"{v:.1f}%"


def score_signal(score):
    try:
        score = int(score)
    except Exception:
        score = 0
    if score >= 70:
        return "🟢 Strong"
    if score >= 45:
        return "🟡 Neutral"
    return "🔴 Weak"


def short_interest_label(v):
    try:
        v = float(v)
    except Exception:
        return "Unknown"
    if v < 5:
        return "Low"
    if v < 10:
        return "Medium"
    if v < 20:
        return "High"
    return "Very high"


def build_scanner_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).copy()
    wanted = [
        "ticker", "score", "price", "vol_ratio", "volume", "avg_volume_20d",
        "insider_buys_90d", "insider_buy_value", "insider_sells_90d",
        "short_interest_pct", "pe_ratio", "market_cap", "sector",
        "industry", "enrich_date", "ownership_form", "short_sale_ratio",
        "top_insider_role"
    ]
    for c in wanted:
        if c not in df.columns:
            df[c] = None
    df["score"] = df["score"].fillna(0).astype(int)
    df["signal"] = df["score"].apply(score_signal)
    df["price"] = df["price"].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "—")
    df["vol_ratio"] = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["volume"] = df["volume"].apply(fmt_int)
    df["avg_volume_20d"] = df["avg_volume_20d"].apply(fmt_int)
    df["insider_buys_90d"] = df["insider_buys_90d"].fillna(0).astype(int)
    df["insider_buy_value"] = df["insider_buy_value"].apply(fmt_money)
    df["insider_sells_90d"] = df["insider_sells_90d"].fillna(0).astype(int)
    df["short_interest_pct"] = df["short_interest_pct"].apply(fmt_pct)
    df["short_sale_ratio"] = df["short_sale_ratio"].apply(fmt_pct)
    df["pe_ratio"] = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    df["market_cap"] = df["market_cap"].apply(fmt_money)
    return df[[
        "ticker", "score", "signal", "price", "vol_ratio", "volume",
        "avg_volume_20d", "insider_buys_90d", "insider_buy_value",
        "insider_sells_90d", "short_interest_pct", "short_sale_ratio",
        "ownership_form", "top_insider_role", "pe_ratio",
        "market_cap", "sector", "industry", "enrich_date"
    ]]


def build_watchlist_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).copy()
    wanted = [
        "ticker", "score", "price", "vol_ratio", "insider_buys_90d",
        "insider_buy_value", "insider_sells_90d", "short_interest_pct",
        "short_sale_ratio", "pe_ratio", "sector", "industry", "enrich_date",
        "ownership_form", "top_insider_role"
    ]
    for c in wanted:
        if c not in df.columns:
            df[c] = None
    df["score"] = df["score"].fillna(0).astype(int)
    df["signal"] = df["score"].apply(score_signal)
    df["price"] = df["price"].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "—")
    df["vol_ratio"] = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["insider_buys_90d"] = df["insider_buys_90d"].fillna(0).astype(int)
    df["insider_buy_value"] = df["insider_buy_value"].apply(fmt_money)
    df["insider_sells_90d"] = df["insider_sells_90d"].fillna(0).astype(int)
    df["short_interest_pct"] = df["short_interest_pct"].apply(fmt_pct)
    df["short_sale_ratio"] = df["short_sale_ratio"].apply(fmt_pct)
    df["pe_ratio"] = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    return df[[
        "ticker", "score", "signal", "price", "vol_ratio",
        "insider_buys_90d", "insider_buy_value", "insider_sells_90d",
        "short_interest_pct", "short_sale_ratio", "ownership_form", "top_insider_role",
        "pe_ratio", "sector", "industry", "enrich_date"
    ]]


def render_kpis(df: pd.DataFrame):
    total = len(df)
    avg_score = int(df["score"].mean()) if total else 0
    top_score = int(df["score"].max()) if total else 0
    top_ticker = df.sort_values("score", ascending=False).iloc[0]["ticker"] if total else "—"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", total)
    c2.metric("Average score", avg_score)
    c3.metric("Top score", top_score)
    c4.metric("Top ticker", top_ticker)


def load_scanner_data(days_back: int, min_score: int):
    try:
        return get_enriched(days_back=days_back, min_score=min_score)
    except Exception as e:
        st.error(f"Eroare conexiune DB: {e}")
        st.stop()


def load_watchlist_data():
    try:
        return get_watchlist(), get_watchlist_enriched()
    except Exception as e:
        st.error(f"Eroare conexiune DB: {e}")
        st.stop()


def show_ticker_panel(ticker: str):
    history = get_ticker_history(ticker, limit=10)
    if not history:
        st.info("Nu există istoric pentru tickerul selectat.")
        return

    latest = history[-1]
    prev = history[-2] if len(history) >= 2 else None
    score_delta = latest.get("score", 0) - (prev.get("score", 0) if prev else 0)

    st.markdown("<div class='section-title'>Ticker Intelligence</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ticker", latest.get("ticker", "—"))
    c2.metric("Score", latest.get("score", 0), delta=score_delta)
    c3.metric("Vol ratio", f"{float(latest.get('vol_ratio') or 0):.2f}x" if latest.get("vol_ratio") is not None else "—")
    c4.metric("Short interest", fmt_pct(latest.get("short_interest_pct")))

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Volume", latest.get("score_volume", 0))
    c2.metric("Insider", latest.get("score_insider", 0))
    c3.metric("Insider quality", latest.get("score_insider_quality", 0))
    c4.metric("Ownership", latest.get("score_ownership", 0))
    c5.metric("Short int", latest.get("score_short_interest", 0))
    c6.metric("Short flow", latest.get("score_short_flow", 0))
    c7.metric("Penalty", latest.get("score_penalty", 0))

    left, right = st.columns([1.25, 1])
    with left:
        hist_df = pd.DataFrame(history)
        chart_df = hist_df[["enrich_date", "score"]].copy()
        chart_df["enrich_date"] = pd.to_datetime(chart_df["enrich_date"])
        chart_df = chart_df.set_index("enrich_date")
        st.line_chart(chart_df, height=220, width="stretch")

        display_cols = [
            "enrich_date", "score", "vol_ratio", "insider_buys_90d",
            "insider_buy_value", "insider_sells_90d", "short_interest_pct",
            "short_sale_ratio", "ownership_form"
        ]
        display = hist_df[display_cols].copy()
        display["insider_buy_value"] = display["insider_buy_value"].apply(fmt_money)
        display["short_interest_pct"] = display["short_interest_pct"].apply(fmt_pct)
        display["short_sale_ratio"] = display["short_sale_ratio"].apply(fmt_pct)
        display["vol_ratio"] = display["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
        st.dataframe(display, width="stretch", hide_index=True)

    with right:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"**Volume signal:** {latest.get('volume_signal') or '—'}")
        st.markdown(f"**Insider signal:** {latest.get('insider_signal') or '—'}")
        st.markdown(f"**Insider role:** {latest.get('top_insider_role') or '—'}")
        st.markdown(f"**Ownership signal:** {latest.get('ownership_signal') or '—'}")
        if latest.get("ownership_pct") is not None:
            st.markdown(f"**Ownership pct:** {fmt_pct(latest.get('ownership_pct'))}")
        st.markdown(f"**Short signal:** {latest.get('short_signal') or '—'}")
        st.markdown(f"**Short flow signal:** {latest.get('short_flow_signal') or '—'}")
        st.markdown(f"**Thesis:** {latest.get('thesis') or '—'}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Interpretare rapidă**")
        st.markdown(f"- Short interest: **{short_interest_label(latest.get('short_interest_pct'))}**")
        st.markdown("- Vol ratio > 2x = unusual, > 5x = extreme")
        st.markdown("- 13D = mai puternic decât 13G")
        st.markdown("- CEO/CFO buy > director buy")
        st.markdown("- Daily short sale ratio > 60% = presiune short ridicată")
        st.markdown("</div>", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("## 📈 Smart Money Screener")
    st.caption(f"Astăzi: {date.today().strftime('%d %b %Y')}")
    st.divider()

    st.markdown("### Scanner Filters")
    min_score = st.slider("Score minim", 0, 100, 30, 5)
    days_back = st.selectbox("Perioada", [1, 2, 3, 5, 10], format_func=lambda x: f"Ultimele {x} zile")
    search_ticker = st.text_input("Caută ticker", placeholder="ex: NVDA").upper().strip()

    st.divider()
    st.markdown("### Legendă")
    st.caption("Score 70+ = strong")
    st.caption("Vol ratio >2x = unusual, >5x = extreme")
    st.caption("Short interest <5% low, >10% elevated")
    st.caption("13D > 13G ca valoare de semnal")
    st.caption("Short sale ratio >60% = short pressure")
    st.caption("CEO/CFO buy > director buy")

st.markdown("""
<div class="hero">
    <div class="hero-title">Smart Money Screener</div>
    <div class="hero-sub">
        Scanner premium pentru semnale smart money • read-only din Supabase • focus pe scor, volum, ownership și insider activity
    </div>
</div>
""", unsafe_allow_html=True)

tab_scanner, tab_watchlist = st.tabs(["Scanner", "Watchlist"])

with tab_scanner:
    raw = load_scanner_data(days_back=days_back, min_score=min_score)
    df = build_scanner_df(raw)
    if search_ticker and not df.empty:
        df = df[df["ticker"].str.contains(search_ticker, case=False, na=False)]

    st.markdown('<div class="section-title">Scanner Overview</div>', unsafe_allow_html=True)
    if df.empty:
        st.info("Niciun candidat pentru filtrele curente.")
    else:
        render_kpis(df)
        top5 = df.sort_values("score", ascending=False).head(5)[["ticker", "score", "vol_ratio", "insider_buys_90d"]]
        st.markdown('<div class="small-muted">Top 5 după scor</div>', unsafe_allow_html=True)
        st.dataframe(top5.rename(columns={"ticker": "Ticker", "score": "Score", "vol_ratio": "Vol Ratio", "insider_buys_90d": "Buys 90d"}), width="stretch", hide_index=True)

        st.markdown('<div class="section-title">Candidates</div>', unsafe_allow_html=True)
        st.dataframe(df, width="stretch", hide_index=True, height=430)

        ticker_options = df["ticker"].tolist()
        selected_ticker = st.selectbox("Selectează ticker pentru acțiune", ticker_options, key="scanner_select")
        c1, c2, c3 = st.columns([1.2, 1.2, 6])
        with c1:
            if st.button("Add selected", width="stretch", type="primary"):
                if selected_ticker:
                    add_to_watchlist(selected_ticker)
                    st.success(f"{selected_ticker} adăugat în watchlist.")
                    st.rerun()
        with c2:
            if st.button("Refresh page", width="stretch"):
                st.rerun()
        with c3:
            row = df[df["ticker"] == selected_ticker].iloc[0]
            st.markdown(f"<div class='small-muted'>Selectat: <b>{row['ticker']}</b> • Score {row['score']} • Vol {row['vol_ratio']} • Ownership {row['ownership_form']} • Role {row['top_insider_role']}</div>", unsafe_allow_html=True)

        show_ticker_panel(selected_ticker)

with tab_watchlist:
    st.markdown('<div class="section-title">Manage Watchlist</div>', unsafe_allow_html=True)
    with st.form("add_watchlist_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1.4, 3.5, 1.2])
        with c1:
            new_ticker = st.text_input("Ticker", placeholder="ex: NVDA")
        with c2:
            notes = st.text_input("Notes", placeholder="motiv, setup, context")
        with c3:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("Add", width="stretch")
        if submitted:
            ticker = (new_ticker or "").upper().strip()
            if ticker:
                add_to_watchlist(ticker, notes)
                st.success(f"{ticker} adăugat.")
                st.rerun()
            else:
                st.warning("Introdu un ticker valid.")

    wl_raw, wl_enriched = load_watchlist_data()
    df_w = build_watchlist_df(wl_enriched)
    if not wl_raw:
        st.info("Watchlist gol. Adaugă tickere din Scanner sau manual.")
    else:
        total_w = len(wl_raw)
        covered = len(df_w["ticker"].unique()) if not df_w.empty else 0
        missing = sorted(set([w["ticker"] for w in wl_raw]) - set(df_w["ticker"].tolist())) if not df_w.empty else sorted(set([w["ticker"] for w in wl_raw]))
        c1, c2, c3 = st.columns(3)
        c1.metric("Watchlist size", total_w)
        c2.metric("With enrich data", covered)
        c3.metric("Missing latest data", len(missing))
        if missing:
            st.warning("Fără date enrich încă: " + ", ".join(missing))

        st.markdown('<div class="section-title">Watchlist Table</div>', unsafe_allow_html=True)
        if df_w.empty:
            st.info("Tickerele există în watchlist, dar nu au încă date în enriched.")
        else:
            st.dataframe(df_w, width="stretch", hide_index=True, height=430)
            selected_watch_ticker = st.selectbox("Selectează ticker din watchlist", df_w["ticker"].tolist(), key="watchlist_select")
            c1, c2, c3 = st.columns([1.2, 1.2, 6])
            with c1:
                if st.button("Remove selected", width="stretch"):
                    if selected_watch_ticker:
                        remove_from_watchlist(selected_watch_ticker)
                        st.success(f"{selected_watch_ticker} șters din watchlist.")
                        st.rerun()
            with c2:
                if st.button("Reload", width="stretch"):
                    st.rerun()
            with c3:
                row = df_w[df_w["ticker"] == selected_watch_ticker].iloc[0]
                st.markdown(f"<div class='small-muted'>Selectat: <b>{row['ticker']}</b> • Score {row['score']} • Vol {row['vol_ratio']} • Ownership {row['ownership_form']} • Role {row['top_insider_role']}</div>", unsafe_allow_html=True)

            show_ticker_panel(selected_watch_ticker)
