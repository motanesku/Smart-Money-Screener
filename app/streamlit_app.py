"""
Premium Streamlit UI — read-only, citește exclusiv din Supabase.
Nu face niciun API call extern.
Nu schimbă structura proiectului.
"""
import sys
sys.path.insert(0, ".")

from datetime import date
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

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

# ── STYLE ────────────────────────────────────────────────────────────────────

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
.kpi-label {
    color: #9aa4b2;
    font-size: 0.84rem;
    margin-bottom: 2px;
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

# ── HELPERS ──────────────────────────────────────────────────────────────────

def fmt_money(v):
    if v is None or v == 0:
        return "—"
    v = float(v)
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
    return f"{int(v):,}"

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

def score_label(score):
    try:
        score = int(score)
    except Exception:
        score = 0
    if score >= 70:
        return "Strong"
    if score >= 45:
        return "Neutral"
    return "Weak"

def score_color(score):
    try:
        score = int(score)
    except Exception:
        score = 0
    if score >= 70:
        return "#16a34a"
    if score >= 45:
        return "#eab308"
    return "#dc2626"

def make_score_html(score):
    color = score_color(score)
    label = score_label(score)
    return (
        f"<div style='display:flex;align-items:center;gap:8px;'>"
        f"<span style='display:inline-block;padding:4px 10px;border-radius:999px;"
        f"background:{color};color:white;font-weight:700;font-size:12px;'>{int(score)}/100</span>"
        f"<span style='color:#94a3b8;font-size:12px;'>{label}</span>"
        f"</div>"
    )

def safe_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)

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

    df["score_badge"] = df["score"].fillna(0).apply(make_score_html)
    df["price_fmt"] = df["price"].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "—")
    df["vol_ratio_fmt"] = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["volume_fmt"] = df["volume"].apply(fmt_int)
    df["avg_volume_20d_fmt"] = df["avg_volume_20d"].apply(fmt_int)
    df["insider_buy_value_fmt"] = df["insider_buy_value"].apply(fmt_money)
    df["short_interest_pct_fmt"] = df["short_interest_pct"].apply(fmt_pct)
    df["market_cap_fmt"] = df["market_cap"].apply(fmt_money)
    df["pe_ratio_fmt"] = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    df["insider_buys_90d"] = df["insider_buys_90d"].fillna(0).astype(int)
    df["insider_sells_90d"] = df["insider_sells_90d"].fillna(0).astype(int)
    df["score"] = df["score"].fillna(0).astype(int)

    return df[[
        "ticker", "score", "score_badge", "price_fmt", "vol_ratio_fmt", "volume_fmt",
        "avg_volume_20d_fmt", "insider_buys_90d", "insider_buy_value_fmt",
        "insider_sells_90d", "short_interest_pct_fmt", "pe_ratio_fmt",
        "market_cap_fmt", "sector", "industry", "enrich_date"
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
    df["score_badge"] = df["score"].apply(make_score_html)
    df["price_fmt"] = df["price"].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "—")
    df["vol_ratio_fmt"] = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["insider_buy_value_fmt"] = df["insider_buy_value"].apply(fmt_money)
    df["short_interest_pct_fmt"] = df["short_interest_pct"].apply(fmt_pct)
    df["pe_ratio_fmt"] = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    df["insider_buys_90d"] = df["insider_buys_90d"].fillna(0).astype(int)
    df["insider_sells_90d"] = df["insider_sells_90d"].fillna(0).astype(int)

    return df[[
        "ticker", "score", "score_badge", "price_fmt", "vol_ratio_fmt",
        "insider_buys_90d", "insider_buy_value_fmt", "insider_sells_90d",
        "short_interest_pct_fmt", "pe_ratio_fmt", "sector", "industry", "enrich_date"
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

def aggrid_table(df: pd.DataFrame, kind: str):
    if df.empty:
        return {"selected_rows": []}

    gb = GridOptionsBuilder.from_dataframe(df)

    gb.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True,
        min_column_width=90,
    )

    gb.configure_selection(
        selection_mode="single",
        use_checkbox=True,
        pre_selected_rows=[],
    )

    gb.configure_grid_options(
        rowHeight=42,
        headerHeight=42,
        animateRows=True,
        suppressRowClickSelection=False,
    )

    gb.configure_column("ticker", pinned="left", width=110)
    gb.configure_column("score", hide=True)
    gb.configure_column(
        "score_badge",
        header_name="Score",
        width=150,
        filter=False,
        sortable=True,
        cellRenderer=JsCode("function(params) { return params.value; }"),
    )

    if kind == "scanner":
        gb.configure_column("price_fmt", header_name="Price", width=100)
        gb.configure_column("vol_ratio_fmt", header_name="Vol Ratio", width=110)
        gb.configure_column("volume_fmt", header_name="Volume", width=115)
        gb.configure_column("avg_volume_20d_fmt", header_name="Avg Vol 20d", width=125)
        gb.configure_column("insider_buys_90d", header_name="Buys 90d", width=105)
        gb.configure_column("insider_buy_value_fmt", header_name="Buy Value", width=120)
        gb.configure_column("insider_sells_90d", header_name="Sells 90d", width=105)
        gb.configure_column("short_interest_pct_fmt", header_name="Short %", width=100)
        gb.configure_column("pe_ratio_fmt", header_name="P/E", width=90)
        gb.configure_column("market_cap_fmt", header_name="Mkt Cap", width=110)
        gb.configure_column("sector", width=130)
        gb.configure_column("industry", width=160)
        gb.configure_column("enrich_date", header_name="Updated", width=110)
    else:
        gb.configure_column("price_fmt", header_name="Price", width=100)
        gb.configure_column("vol_ratio_fmt", header_name="Vol Ratio", width=110)
        gb.configure_column("insider_buys_90d", header_name="Buys 90d", width=105)
        gb.configure_column("insider_buy_value_fmt", header_name="Buy Value", width=120)
        gb.configure_column("insider_sells_90d", header_name="Sells 90d", width=105)
        gb.configure_column("short_interest_pct_fmt", header_name="Short %", width=100)
        gb.configure_column("pe_ratio_fmt", header_name="P/E", width=90)
        gb.configure_column("sector", width=130)
        gb.configure_column("industry", width=160)
        gb.configure_column("enrich_date", header_name="Updated", width=110)

    grid = AgGrid(
        df,
        gridOptions=gb.build(),
        height=520 if len(df) > 10 else 120 + len(df) * 42,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        theme="streamlit",
        reload_data=False,
    )
    return grid

# ── DATA LOAD ────────────────────────────────────────────────────────────────

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

# ── SIDEBAR ──────────────────────────────────────────────────────────────────

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

# ── HEADER ───────────────────────────────────────────────────────────────────

st.markdown(f"""
<div class="hero">
    <div class="hero-title">Smart Money Screener</div>
    <div class="hero-sub">
        Scanner premium pentru semnale smart money • read-only din Supabase • focus pe scor, volum și insider activity
    </div>
</div>
""", unsafe_allow_html=True)

tab_scanner, tab_watchlist = st.tabs(["Scanner", "Watchlist"])

# ── TAB: SCANNER ─────────────────────────────────────────────────────────────

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

        top5 = df.sort_values("score", ascending=False).head(5)[["ticker", "score", "vol_ratio_fmt", "insider_buys_90d"]]
        st.markdown('<div class="small-muted">Top 5 după scor</div>', unsafe_allow_html=True)
        st.dataframe(
            top5.rename(columns={
                "ticker": "Ticker",
                "score": "Score",
                "vol_ratio_fmt": "Vol Ratio",
                "insider_buys_90d": "Buys 90d",
            }),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown('<div class="section-title">Candidates</div>', unsafe_allow_html=True)
        grid = aggrid_table(df, "scanner")
        selected = grid.get("selected_rows", [])

        c1, c2, c3 = st.columns([1.2, 1.2, 6])
        with c1:
            if st.button("Add selected", use_container_width=True, type="primary"):
                if selected:
                    ticker = selected[0]["ticker"]
                    add_to_watchlist(ticker)
                    st.success(f"{ticker} adăugat în watchlist.")
                    st.rerun()
                else:
                    st.warning("Selectează un ticker din tabel.")
        with c2:
            if st.button("Refresh page", use_container_width=True):
                st.rerun()
        with c3:
            if selected:
                row = selected[0]
                st.markdown(
                    f"<div class='small-muted'>Selectat: <b>{row['ticker']}</b> • Score {row['score']} • "
                    f"Vol {row['vol_ratio_fmt']} • Buy Value {row['insider_buy_value_fmt']}</div>",
                    unsafe_allow_html=True,
                )

# ── TAB: WATCHLIST ───────────────────────────────────────────────────────────

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
            submitted = st.form_submit_button("Add", use_container_width=True)

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
            grid_w = aggrid_table(df_w, "watchlist")
            selected_w = grid_w.get("selected_rows", [])

            c1, c2, c3 = st.columns([1.2, 1.2, 6])
            with c1:
                if st.button("Remove selected", use_container_width=True):
                    if selected_w:
                        ticker = selected_w[0]["ticker"]
                        remove_from_watchlist(ticker)
                        st.success(f"{ticker} șters din watchlist.")
                        st.rerun()
                    else:
                        st.warning("Selectează un ticker din tabel.")
            with c2:
                if st.button("Reload", use_container_width=True):
                    st.rerun()
            with c3:
                if selected_w:
                    row = selected_w[0]
                    st.markdown(
                        f"<div class='small-muted'>Selectat: <b>{row['ticker']}</b> • Score {row['score']} • "
                        f"Vol {row['vol_ratio_fmt']} • Updated {row['enrich_date']}</div>",
                        unsafe_allow_html=True,
                    )
