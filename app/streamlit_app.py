"""
Premium Streamlit UI — stabil pentru Streamlit Cloud.
Păstrează structura proiectului și Supabase backend.
"""
import sys
sys.path.insert(0, ".")

from datetime import date
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from app.db import (
    get_enriched,
    get_watchlist,
    get_watchlist_enriched,
    add_to_watchlist,
    remove_from_watchlist,
)

st.set_page_config(
    page_title="Smart Money Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 1.5rem;
    max-width: 1500px;
}
[data-testid="stMetric"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 14px 16px;
}
.hero {
    padding: 18px 20px;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(36,36,52,0.95), rgba(20,20,30,0.95));
    margin-bottom: 14px;
}
.hero-title {
    font-size: 1.55rem;
    font-weight: 700;
    margin-bottom: 4px;
}
.hero-sub {
    color: #9aa4b2;
    font-size: 0.92rem;
}
.section-title {
    font-size: 1.08rem;
    font-weight: 700;
    margin: 8px 0 10px 0;
}
.small-muted {
    color: #9aa4b2;
    font-size: 0.84rem;
}
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

def score_bucket(score):
    try:
        score = int(score)
    except Exception:
        score = 0
    if score >= 70:
        return "🟢 Strong"
    if score >= 45:
        return "🟡 Neutral"
    return "🔴 Weak"

def build_scanner_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).copy()

    wanted = [
        "ticker", "score", "price", "vol_ratio", "volume", "avg_volume_20d",
        "insider_buys_90d", "insider_buy_value", "insider_sells_90d",
        "short_interest_pct", "pe_ratio", "market_cap", "sector",
        "industry", "enrich_date"
    ]
    for c in wanted:
        if c not in df.columns:
            df[c] = None

    df["score"] = df["score"].fillna(0).astype(int)
    df["signal"] = df["score"].apply(score_bucket)
    df["price"] = df["price"].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "—")
    df["vol_ratio"] = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["volume"] = df["volume"].apply(fmt_int)
    df["avg_volume_20d"] = df["avg_volume_20d"].apply(fmt_int)
    df["insider_buys_90d"] = df["insider_buys_90d"].fillna(0).astype(int)
    df["insider_buy_value"] = df["insider_buy_value"].apply(fmt_money)
    df["insider_sells_90d"] = df["insider_sells_90d"].fillna(0).astype(int)
    df["short_interest_pct"] = df["short_interest_pct"].apply(fmt_pct)
    df["pe_ratio"] = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    df["market_cap"] = df["market_cap"].apply(fmt_money)

    return df[[
        "ticker", "score", "signal", "price", "vol_ratio", "volume",
        "avg_volume_20d", "insider_buys_90d", "insider_buy_value",
        "insider_sells_90d", "short_interest_pct", "pe_ratio",
        "market_cap", "sector", "industry", "enrich_date"
    ]]

def build_watchlist_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).copy()

    wanted = [
        "ticker", "score", "price", "vol_ratio", "insider_buys_90d",
        "insider_buy_value", "insider_sells_90d", "short_interest_pct",
        "pe_ratio", "sector", "industry", "enrich_date"
    ]
    for c in wanted:
        if c not in df.columns:
            df[c] = None

    df["score"] = df["score"].fillna(0).astype(int)
    df["signal"] = df["score"].apply(score_bucket)
    df["price"] = df["price"].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "—")
    df["vol_ratio"] = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["insider_buys_90d"] = df["insider_buys_90d"].fillna(0).astype(int)
    df["insider_buy_value"] = df["insider_buy_value"].apply(fmt_money)
    df["insider_sells_90d"] = df["insider_sells_90d"].fillna(0).astype(int)
    df["short_interest_pct"] = df["short_interest_pct"].apply(fmt_pct)
    df["pe_ratio"] = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")

    return df[[
        "ticker", "score", "signal", "price", "vol_ratio",
        "insider_buys_90d", "insider_buy_value", "insider_sells_90d",
        "short_interest_pct", "pe_ratio", "sector", "industry", "enrich_date"
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

def aggrid_table(df: pd.DataFrame, key: str):
    if df.empty:
        return {"selected_rows": []}

    gb = GridOptionsBuilder.from_dataframe(df)

    gb.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True,
        min_column_width=95,
    )

    gb.configure_selection(
        selection_mode="single",
        use_checkbox=True,
    )

    gb.configure_grid_options(
        rowHeight=38,
        headerHeight=40,
        animateRows=True,
        domLayout="normal",
    )

    gb.configure_column("ticker", pinned="left", width=110)
    gb.configure_column("score", width=95, type=["numericColumn"])
    gb.configure_column("signal", width=130)
    gb.configure_column("price", width=90)
    gb.configure_column("vol_ratio", width=100)
    gb.configure_column("volume", width=115)
    gb.configure_column("avg_volume_20d", header_name="Avg Vol 20d", width=125)
    gb.configure_column("insider_buys_90d", header_name="Buys 90d", width=100)
    gb.configure_column("insider_buy_value", header_name="Buy Value", width=115)
    gb.configure_column("insider_sells_90d", header_name="Sells 90d", width=100)
    gb.configure_column("short_interest_pct", header_name="Short %", width=95)
    gb.configure_column("pe_ratio", header_name="P/E", width=85)
    if "market_cap" in df.columns:
        gb.configure_column("market_cap", header_name="Mkt Cap", width=110)
    gb.configure_column("sector", width=130)
    gb.configure_column("industry", width=160)
    gb.configure_column("enrich_date", header_name="Updated", width=110)

    grid = AgGrid(
        df,
        gridOptions=gb.build(),
        height=420,
        fit_columns_on_grid_load=False,
        update_on=["selectionChanged"],
        theme="balham",
        key=key,
    )
    return grid or {"selected_rows": []}

def normalize_selected(grid_result):
    if not grid_result:
        return []
    selected = grid_result.get("selected_rows", [])
    if selected is None:
        return []
    if isinstance(selected, pd.DataFrame):
        return selected.to_dict("records")
    return selected

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

with st.sidebar:
    st.markdown("## 📈 Smart Money Screener")
    st.caption(f"Astăzi: {date.today().strftime('%d %b %Y')}")
    st.divider()

    st.markdown("### Scanner Filters")
    min_score = st.slider("Score minim", 0, 100, 30, 5)
    days_back = st.selectbox("Perioada", [1, 2, 3, 5], format_func=lambda x: f"Ultimele {x} zile")
    search_ticker = st.text_input("Caută ticker", placeholder="ex: NVDA").upper().strip()

    st.divider()
    st.markdown("### Info")
    st.caption("Actualizat 2x/zi via GitHub Actions")
    st.caption("08:45 ET — enrich dimineața")
    st.caption("16:30 ET — enrich după închidere")

st.markdown("""
<div class="hero">
    <div class="hero-title">Smart Money Screener</div>
    <div class="hero-sub">
        Scanner premium pentru semnale smart money • read-only din Supabase • focus pe scor, volum și insider activity
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
        st.dataframe(
            top5.rename(columns={
                "ticker": "Ticker",
                "score": "Score",
                "vol_ratio": "Vol Ratio",
                "insider_buys_90d": "Buys 90d",
            }),
            width="stretch",
            hide_index=True,
        )

        st.markdown('<div class="section-title">Candidates</div>', unsafe_allow_html=True)
        grid = aggrid_table(df, "scanner_grid")
        selected = normalize_selected(grid)

        c1, c2, c3 = st.columns([1.2, 1.2, 6])
        with c1:
            if st.button("Add selected", width="stretch", type="primary"):
                if selected:
                    ticker = selected[0]["ticker"]
                    add_to_watchlist(ticker)
                    st.success(f"{ticker} adăugat în watchlist.")
                    st.rerun()
                else:
                    st.warning("Selectează un ticker din tabel.")
        with c2:
            if st.button("Refresh page", width="stretch"):
                st.rerun()
        with c3:
            if selected:
                row = selected[0]
                st.markdown(
                    f"<div class='small-muted'>Selectat: <b>{row['ticker']}</b> • Score {row['score']} • "
                    f"Vol {row['vol_ratio']} • Buy Value {row['insider_buy_value']}</div>",
                    unsafe_allow_html=True,
                )

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
            grid_w = aggrid_table(df_w, "watchlist_grid")
            selected_w = normalize_selected(grid_w)

            c1, c2, c3 = st.columns([1.2, 1.2, 6])
            with c1:
                if st.button("Remove selected", width="stretch"):
                    if selected_w:
                        ticker = selected_w[0]["ticker"]
                        remove_from_watchlist(ticker)
                        st.success(f"{ticker} șters din watchlist.")
                        st.rerun()
                    else:
                        st.warning("Selectează un ticker din tabel.")
            with c2:
                if st.button("Reload", width="stretch"):
                    st.rerun()
            with c3:
                if selected_w:
                    row = selected_w[0]
                    st.markdown(
                        f"<div class='small-muted'>Selectat: <b>{row['ticker']}</b> • Score {row['score']} • "
                        f"Vol {row['vol_ratio']} • Updated {row['enrich_date']}</div>",
                        unsafe_allow_html=True,
                    )
