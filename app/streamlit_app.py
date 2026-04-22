"""
Smart Money Screener — UI compact, dens, fără scroll inutil.
Compatibil Streamlit Community Cloud.
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

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Smart Money Screener",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif !important;
    background: #0a0c10 !important;
    color: #c9d1d9 !important;
}

.block-container {
    padding: 1rem 1.5rem 1rem 1.5rem !important;
    max-width: 1600px !important;
}

/* Sidebar colaps */
[data-testid="collapsedControl"] { display: none; }

/* Header bar */
.smm-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 18px;
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    margin-bottom: 14px;
}
.smm-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1rem;
    font-weight: 600;
    color: #58a6ff;
    letter-spacing: 0.04em;
}
.smm-subtitle {
    font-size: 0.75rem;
    color: #484f58;
    font-family: 'IBM Plex Mono', monospace;
}
.smm-date {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #484f58;
}

/* Stat bar */
.stat-row {
    display: flex;
    gap: 10px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}
.stat-box {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 8px 16px;
    min-width: 110px;
    flex: 1;
}
.stat-label {
    font-size: 0.65rem;
    color: #484f58;
    font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 2px;
}
.stat-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.15rem;
    font-weight: 600;
    color: #e6edf3;
}
.stat-value.green { color: #3fb950; }
.stat-value.yellow { color: #d29922; }
.stat-value.blue { color: #58a6ff; }

/* Filter bar inline */
.filter-bar {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 12px;
    display: flex;
    gap: 14px;
    align-items: center;
    flex-wrap: wrap;
}

/* Signals inline */
.sig {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    padding: 2px 7px;
    border-radius: 4px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.sig-strong { background: #1a2d1a; color: #3fb950; border: 1px solid #238636; }
.sig-neutral { background: #2d2200; color: #d29922; border: 1px solid #9e6a03; }
.sig-weak { background: #2d1a1a; color: #f85149; border: 1px solid #da3633; }
.sig-na { background: #161b22; color: #484f58; border: 1px solid #21262d; }

/* Ticker panel */
.ticker-panel {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 14px 16px;
    margin-top: 10px;
}
.panel-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #484f58;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
    border-bottom: 1px solid #21262d;
    padding-bottom: 6px;
}

/* Score breakdown bar */
.score-bar-wrap { margin: 6px 0; }
.score-bar-label {
    display: flex;
    justify-content: space-between;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    color: #8b949e;
    margin-bottom: 2px;
}
.score-bar-track {
    background: #161b22;
    border-radius: 3px;
    height: 6px;
    width: 100%;
    overflow: hidden;
}
.score-bar-fill {
    height: 6px;
    border-radius: 3px;
    transition: width 0.4s ease;
}

/* Signal pill list */
.signal-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 5px 0;
    border-bottom: 1px solid #161b22;
    font-size: 0.78rem;
}
.signal-key {
    font-family: 'IBM Plex Mono', monospace;
    color: #484f58;
    min-width: 130px;
    font-size: 0.72rem;
}
.signal-val { color: #c9d1d9; }

/* Thesis box */
.thesis-box {
    background: #161b22;
    border-left: 3px solid #58a6ff;
    border-radius: 0 6px 6px 0;
    padding: 8px 12px;
    font-size: 0.78rem;
    color: #8b949e;
    margin-top: 8px;
    font-style: italic;
}

/* Dataframe overrides */
[data-testid="stDataFrame"] {
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
}

/* Tab styling */
[data-baseweb="tab-list"] {
    background: #0d1117 !important;
    border-bottom: 1px solid #21262d !important;
    gap: 0 !important;
}
[data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    color: #484f58 !important;
    padding: 8px 18px !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    color: #58a6ff !important;
    border-bottom: 2px solid #58a6ff !important;
}

/* Metrics compact */
[data-testid="stMetric"] {
    background: #0d1117 !important;
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
}
[data-testid="stMetricLabel"] { font-size: 0.65rem !important; color: #484f58 !important; }
[data-testid="stMetricValue"] { font-size: 1rem !important; font-family: 'IBM Plex Mono', monospace !important; }

/* Slider */
[data-testid="stSlider"] label { font-size: 0.75rem !important; }

/* Buttons */
.stButton > button {
    background: #21262d !important;
    border: 1px solid #30363d !important;
    color: #c9d1d9 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.72rem !important;
    border-radius: 6px !important;
    padding: 4px 14px !important;
}
.stButton > button:hover {
    background: #30363d !important;
    border-color: #58a6ff !important;
    color: #58a6ff !important;
}
.stButton > button[kind="primary"] {
    background: #1f4a1f !important;
    border-color: #238636 !important;
    color: #3fb950 !important;
}

/* Selectbox */
[data-baseweb="select"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.75rem !important;
}

/* Text input */
.stTextInput input {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.75rem !important;
    background: #0d1117 !important;
    border: 1px solid #30363d !important;
    color: #c9d1d9 !important;
}

/* Info/warning */
[data-testid="stAlert"] { font-size: 0.78rem !important; }

/* Divider */
hr { border-color: #21262d !important; }
</style>
""", unsafe_allow_html=True)


# ── Formatters ─────────────────────────────────────────────────────────────────
def fmt_money(v):
    if v is None:
        return "—"
    try:
        v = float(v)
    except Exception:
        return "—"
    if v == 0:
        return "—"
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
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
    if v == 0:
        return "—"
    if 0 < abs(v) < 1:
        return f"{v*100:.1f}%"
    return f"{v:.1f}%"

def fmt_price(v):
    if v is None:
        return "—"
    try:
        return f"${float(v):.2f}"
    except Exception:
        return "—"

def fmt_ratio(v):
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}x"
    except Exception:
        return "—"

def score_badge(score):
    try:
        s = int(score)
    except Exception:
        s = 0
    if s >= 70:
        return f'<span class="sig sig-strong">▲ {s}</span>'
    if s >= 45:
        return f'<span class="sig sig-neutral">◆ {s}</span>'
    return f'<span class="sig sig-weak">▼ {s}</span>'

def score_class(score):
    try:
        s = int(score)
    except Exception:
        s = 0
    if s >= 70:
        return "green"
    if s >= 45:
        return "yellow"
    return ""

def vol_badge(ratio):
    try:
        r = float(ratio)
    except Exception:
        return "—"
    if r >= 5:
        return f'<span class="sig sig-strong">{r:.1f}x 🔥</span>'
    if r >= 3:
        return f'<span class="sig sig-neutral">{r:.1f}x</span>'
    if r >= 2:
        return f'<span class="sig sig-na">{r:.1f}x</span>'
    return f'<span class="sig sig-na">{r:.1f}x</span>'

def score_bar_html(label, value, max_val, color="#58a6ff"):
    pct = min(100, int((value / max_val) * 100)) if max_val > 0 else 0
    neg = value < 0
    bar_color = "#f85149" if neg else color
    pct = abs(pct)
    return f"""
<div class="score-bar-wrap">
  <div class="score-bar-label"><span>{label}</span><span style="color:{bar_color}">{value:+d}</span></div>
  <div class="score-bar-track"><div class="score-bar-fill" style="width:{pct}%;background:{bar_color}"></div></div>
</div>"""

def signal_row_html(key, val):
    return f'<div class="signal-row"><span class="signal-key">{key}</span><span class="signal-val">{val or "—"}</span></div>'


# ── Data loaders ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_scanner(days_back, min_score):
    try:
        return get_enriched(days_back=days_back, min_score=min_score)
    except Exception as e:
        st.error(f"DB error: {e}")
        return []

@st.cache_data(ttl=300)
def load_watchlist_data():
    try:
        return get_watchlist(), get_watchlist_enriched()
    except Exception as e:
        st.error(f"DB error: {e}")
        return [], []

@st.cache_data(ttl=120)
def load_history(ticker):
    return get_ticker_history(ticker, limit=10)


# ── DataFrame builder ──────────────────────────────────────────────────────────
def build_df(rows):
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).copy()
    cols_needed = [
        "ticker", "score", "price", "vol_ratio", "volume", "avg_volume_20d",
        "insider_buys_90d", "insider_buy_value", "insider_sells_90d",
        "short_interest_pct", "short_sale_ratio", "pe_ratio",
        "market_cap", "sector", "top_insider_role", "ownership_form",
        "enrich_date"
    ]
    for c in cols_needed:
        if c not in df.columns:
            df[c] = None
    df["score"] = df["score"].fillna(0).astype(int)
    df["Display Price"] = df["price"].apply(fmt_price)
    df["Vol Ratio"] = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["Volume"] = df["volume"].apply(fmt_int)
    df["Avg Vol 20d"] = df["avg_volume_20d"].apply(fmt_int)
    df["Buys 90d"] = df["insider_buys_90d"].fillna(0).astype(int)
    df["Buy Value"] = df["insider_buy_value"].apply(fmt_money)
    df["Sells 90d"] = df["insider_sells_90d"].fillna(0).astype(int)
    df["Short %"] = df["short_interest_pct"].apply(fmt_pct)
    df["Short Flow"] = df["short_sale_ratio"].apply(fmt_pct)
    df["P/E"] = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    df["Mkt Cap"] = df["market_cap"].apply(fmt_money)
    df["Date"] = df["enrich_date"]
    return df


# ── Ticker detail panel ────────────────────────────────────────────────────────
def render_ticker_panel(ticker: str):
    history = load_history(ticker)
    if not history:
        st.info("Nu există istoric pentru acest ticker.")
        return

    latest = history[-1]
    prev = history[-2] if len(history) >= 2 else None
    score_delta = latest.get("score", 0) - (prev.get("score", 0) if prev else 0)

    st.markdown(f'<div class="panel-header">📊 {ticker} · Intelligence Panel</div>', unsafe_allow_html=True)

    # Row 1 — 4 key metrics compact
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Score", latest.get("score", 0), delta=score_delta)
    c2.metric("Price", fmt_price(latest.get("price")))
    c3.metric("Vol Ratio", fmt_ratio(latest.get("vol_ratio")))
    c4.metric("Short Interest", fmt_pct(latest.get("short_interest_pct")))
    c5.metric("Mkt Cap", fmt_money(latest.get("market_cap")))

    left, mid, right = st.columns([1.8, 1.4, 1.4])

    with left:
        # Score breakdown mini bars
        st.markdown("**Score Breakdown**")
        sv = int(latest.get("score_volume") or 0)
        si = int(latest.get("score_insider") or 0)
        sq = int(latest.get("score_insider_quality") or 0)
        so = int(latest.get("score_ownership") or 0)
        ss = int(latest.get("score_short_interest") or 0)
        sf = int(latest.get("score_short_flow") or 0)
        sp = int(latest.get("score_penalty") or 0)
        bars = (
            score_bar_html("Volume", sv, 25, "#58a6ff") +
            score_bar_html("Insider qty", si, 35, "#3fb950") +
            score_bar_html("Insider quality", sq, 20, "#3fb950") +
            score_bar_html("Ownership", so, 15, "#79c0ff") +
            score_bar_html("Short interest", ss, 10, "#d29922") +
            score_bar_html("Short flow", sf, 10, "#d29922") +
            score_bar_html("Penalty", sp, 0, "#f85149")
        )
        st.markdown(f'<div class="ticker-panel">{bars}</div>', unsafe_allow_html=True)

        # History chart — compact
        if len(history) > 1:
            hist_df = pd.DataFrame(history)
            chart_df = hist_df[["enrich_date", "score"]].copy()
            chart_df["enrich_date"] = pd.to_datetime(chart_df["enrich_date"])
            chart_df = chart_df.set_index("enrich_date")
            st.line_chart(chart_df, height=130, use_container_width=True)

    with mid:
        st.markdown("**Semnale**")
        signals_html = (
            signal_row_html("Volume", latest.get("volume_signal")) +
            signal_row_html("Insider", latest.get("insider_signal")) +
            signal_row_html("Insider role", latest.get("top_insider_role")) +
            signal_row_html("Ownership", latest.get("ownership_signal")) +
            signal_row_html("Ownership form", latest.get("ownership_form")) +
            signal_row_html("Ownership pct", fmt_pct(latest.get("ownership_pct"))) +
            signal_row_html("Short int", latest.get("short_signal")) +
            signal_row_html("Short flow", latest.get("short_flow_signal"))
        )
        thesis = latest.get("thesis") or ""
        st.markdown(
            f'<div class="ticker-panel">{signals_html}'
            f'<div class="thesis-box">{thesis}</div></div>',
            unsafe_allow_html=True
        )

    with right:
        st.markdown("**Istoric (10 zile)**")
        if len(history) > 0:
            hist_df = pd.DataFrame(history)
            show_cols = ["enrich_date", "score", "vol_ratio", "insider_buys_90d", "insider_buy_value", "short_interest_pct"]
            for c in show_cols:
                if c not in hist_df.columns:
                    hist_df[c] = None
            hist_display = hist_df[show_cols].copy()
            hist_display["vol_ratio"] = hist_display["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
            hist_display["insider_buy_value"] = hist_display["insider_buy_value"].apply(fmt_money)
            hist_display["short_interest_pct"] = hist_display["short_interest_pct"].apply(fmt_pct)
            hist_display.columns = ["Date", "Score", "Vol", "Buys", "Buy$", "SI%"]
            st.dataframe(hist_display, hide_index=True, use_container_width=True, height=220)

        # Quick guide compact
        st.markdown("""
<div class="ticker-panel" style="margin-top:8px">
<div class="panel-header">Referință rapidă</div>
<div style="font-size:0.72rem;color:#484f58;font-family:'IBM Plex Mono',monospace;line-height:1.8">
Score ≥70 → strong<br>
Vol ≥5x → extreme spike<br>
SI &lt;5% → low pressure<br>
13D &gt; 13G ca semnal<br>
CEO/CFO &gt; Director<br>
Short flow &gt;60% → presiune
</div>
</div>
""", unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="smm-header">
  <div>
    <div class="smm-title">📡 SMART MONEY SCREENER</div>
    <div class="smm-subtitle">volume spikes · insider activity · short flows · ownership signals</div>
  </div>
  <div class="smm-date">{date.today().strftime('%d %b %Y')}</div>
</div>
""", unsafe_allow_html=True)


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_scan, tab_watch = st.tabs(["Scanner", "Watchlist"])


# ══ SCANNER TAB ════════════════════════════════════════════════════════════════
with tab_scan:
    # Inline filters — nu sidebar
    fc1, fc2, fc3, fc4, fc5 = st.columns([1, 1, 1.2, 1.5, 3])
    with fc1:
        min_score = st.slider("Score min", 0, 100, 30, 5)
    with fc2:
        days_back = st.selectbox("Perioadă", [1, 2, 3, 5, 10],
                                  format_func=lambda x: f"{x}d")
    with fc3:
        sector_filter = st.text_input("Sector", placeholder="ex: Technology")
    with fc4:
        search_ticker = st.text_input("Ticker search", placeholder="ex: NVDA").upper().strip()
    with fc5:
        st.write("")  # spacer

    raw = load_scanner(days_back, min_score)
    df_full = build_df(raw)

    # Apply filters
    df = df_full.copy()
    if not df.empty:
        if search_ticker:
            df = df[df["ticker"].str.contains(search_ticker, case=False, na=False)]
        if sector_filter:
            df = df[df["sector"].str.contains(sector_filter, case=False, na=False)]

    # KPI bar
    if not df.empty:
        total = len(df)
        avg_s = int(df["score"].mean())
        top_t = df.nlargest(1, "score").iloc[0]["ticker"]
        top_s = int(df["score"].max())
        strong = int((df["score"] >= 70).sum())
        neutral = int(((df["score"] >= 45) & (df["score"] < 70)).sum())
        weak = int((df["score"] < 45).sum())

        st.markdown(f"""
<div class="stat-row">
  <div class="stat-box"><div class="stat-label">Candidates</div><div class="stat-value blue">{total}</div></div>
  <div class="stat-box"><div class="stat-label">Avg Score</div><div class="stat-value">{avg_s}</div></div>
  <div class="stat-box"><div class="stat-label">Top Ticker</div><div class="stat-value blue">{top_t}</div></div>
  <div class="stat-box"><div class="stat-label">Top Score</div><div class="stat-value {score_class(top_s)}">{top_s}</div></div>
  <div class="stat-box"><div class="stat-label">▲ Strong ≥70</div><div class="stat-value green">{strong}</div></div>
  <div class="stat-box"><div class="stat-label">◆ Neutral 45-70</div><div class="stat-value yellow">{neutral}</div></div>
  <div class="stat-box"><div class="stat-label">▼ Weak &lt;45</div><div class="stat-value">{weak}</div></div>
</div>
""", unsafe_allow_html=True)

        # Main table — compact columns
        display_df = df[[
            "ticker", "score", "Display Price", "Vol Ratio", "Volume",
            "Buys 90d", "Buy Value", "Sells 90d", "Short %", "Short Flow",
            "ownership_form", "top_insider_role", "P/E", "Mkt Cap",
            "sector", "Date"
        ]].rename(columns={
            "ticker": "Ticker",
            "score": "Score",
            "Display Price": "Price",
            "ownership_form": "Form",
            "top_insider_role": "Role",
            "sector": "Sector",
        })

        st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True,
            height=320,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"
                ),
            }
        )

        # Action row
        ac1, ac2, ac3, ac4 = st.columns([2, 1.2, 1.2, 5])
        with ac1:
            ticker_options = df["ticker"].tolist()
            selected_ticker = st.selectbox("Selectează ticker", ticker_options, key="scan_sel", label_visibility="collapsed")
        with ac2:
            if st.button("➕ Add to watchlist", type="primary"):
                add_to_watchlist(selected_ticker)
                st.success(f"{selected_ticker} adăugat.")
                st.cache_data.clear()
                st.rerun()
        with ac3:
            if st.button("🔄 Refresh"):
                st.cache_data.clear()
                st.rerun()
        with ac4:
            row = df[df["ticker"] == selected_ticker].iloc[0]
            st.markdown(
                f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.72rem;color:#484f58;padding-top:8px">'
                f'{row["ticker"]} · score <b style="color:#c9d1d9">{row["score"]}</b> · '
                f'{row["Vol Ratio"]} vol · {row["Form"] if row["Form"] != "—" else "no form"} · '
                f'{row["Role"]}</div>',
                unsafe_allow_html=True
            )

        # Ticker panel below table
        st.markdown("---")
        render_ticker_panel(selected_ticker)

    else:
        st.info("Niciun candidat pentru filtrele curente.")


# ══ WATCHLIST TAB ══════════════════════════════════════════════════════════════
with tab_watch:
    # Add form — compact inline
    wc1, wc2, wc3, wc4 = st.columns([1.5, 3, 1.5, 4])
    with wc1:
        new_ticker = st.text_input("Ticker", placeholder="ex: NVDA", key="wl_ticker")
    with wc2:
        notes = st.text_input("Notes", placeholder="setup, motiv, context", key="wl_notes")
    with wc3:
        st.write("")
        st.write("")
        if st.button("➕ Add", type="primary"):
            t = (new_ticker or "").upper().strip()
            if t:
                add_to_watchlist(t, notes)
                st.success(f"{t} adăugat.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Ticker invalid.")
    with wc4:
        st.write("")

    wl_raw, wl_enriched = load_watchlist_data()
    df_w_full = build_df(wl_enriched)

    if not wl_raw:
        st.info("Watchlist gol. Adaugă tickers din Scanner sau manual.")
    else:
        total_w = len(wl_raw)
        covered = len(df_w_full["ticker"].unique()) if not df_w_full.empty else 0
        missing_set = set(w["ticker"] for w in wl_raw) - set(df_w_full["ticker"].tolist() if not df_w_full.empty else [])

        st.markdown(f"""
<div class="stat-row">
  <div class="stat-box"><div class="stat-label">Watchlist</div><div class="stat-value blue">{total_w}</div></div>
  <div class="stat-box"><div class="stat-label">Cu date enrich</div><div class="stat-value green">{covered}</div></div>
  <div class="stat-box"><div class="stat-label">Fără date</div><div class="stat-value">{len(missing_set)}</div></div>
</div>
""", unsafe_allow_html=True)

        if missing_set:
            st.warning("Fără date: " + ", ".join(sorted(missing_set)))

        if not df_w_full.empty:
            display_w = df_w_full[[
                "ticker", "score", "Display Price", "Vol Ratio", "Buys 90d",
                "Buy Value", "Sells 90d", "Short %", "Short Flow",
                "ownership_form", "top_insider_role", "P/E", "sector", "Date"
            ]].rename(columns={
                "ticker": "Ticker", "score": "Score",
                "Display Price": "Price",
                "ownership_form": "Form", "top_insider_role": "Role", "sector": "Sector"
            })

            st.dataframe(
                display_w,
                hide_index=True,
                use_container_width=True,
                height=280,
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Score", min_value=0, max_value=100, format="%d"
                    ),
                }
            )

            wac1, wac2, wac3, wac4 = st.columns([2, 1.2, 1.2, 5])
            with wac1:
                selected_w = st.selectbox("Selectează", df_w_full["ticker"].tolist(), key="wl_sel", label_visibility="collapsed")
            with wac2:
                if st.button("🗑 Remove"):
                    remove_from_watchlist(selected_w)
                    st.success(f"{selected_w} șters.")
                    st.cache_data.clear()
                    st.rerun()
            with wac3:
                if st.button("🔄 Reload"):
                    st.cache_data.clear()
                    st.rerun()
            with wac4:
                row_w = df_w_full[df_w_full["ticker"] == selected_w].iloc[0]
                st.markdown(
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.72rem;color:#484f58;padding-top:8px">'
                    f'{row_w["ticker"]} · score <b style="color:#c9d1d9">{row_w["score"]}</b> · '
                    f'{row_w["Vol Ratio"]} vol · {row_w["Form"] if row_w["Form"] != "—" else "no form"} · '
                    f'{row_w["Role"]}</div>',
                    unsafe_allow_html=True
                )

            st.markdown("---")
            render_ticker_panel(selected_w)
