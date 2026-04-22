"""
Smart Money Screener — v7
+ Company name în tabel și watchlist
+ Haiku AI interpretare per ticker (în panoul de detaliu)
+ Layout fix: coloane prioritizate, responsive
+ Score rămâne algoritmic, Haiku doar interpretează
"""
import sys
sys.path.insert(0, ".")

import os
import json
import requests
from datetime import date
import pandas as pd
import streamlit as st

from app.db import (
    get_enriched, get_watchlist, get_watchlist_enriched,
    get_ticker_history, add_to_watchlist, remove_from_watchlist,
)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

st.set_page_config(
    page_title="Smart Money Screener",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

dark = st.session_state.dark_mode

if dark:
    BG="#0a0c10"; BG2="#0d1117"; BG3="#161b22"
    BORDER="#21262d"; BORDER2="#30363d"
    TEXT="#c9d1d9"; TEXT2="#e6edf3"
    MUTED="#484f58"; MUTED2="#8b949e"
    ACCENT="#58a6ff"; GREEN="#3fb950"; YELLOW="#d29922"; RED="#f85149"
    SS_BG="#1a2d1a"; SS_BD="#238636"; SS_TX="#3fb950"
    SN_BG="#2d2200"; SN_BD="#9e6a03"; SN_TX="#d29922"
    SW_BG="#2d1a1a"; SW_BD="#da3633"; SW_TX="#f85149"
    SA_BG="#161b22"; SA_BD="#21262d"; SA_TX="#484f58"
    AI_BG="#0d1b2a"; AI_BD="#1f6feb"; AI_TX="#58a6ff"
else:
    BG="#f6f8fa"; BG2="#ffffff"; BG3="#eaeef2"
    BORDER="#d0d7de"; BORDER2="#b0bec5"
    TEXT="#1c1f23"; TEXT2="#0d1117"
    MUTED="#8c959f"; MUTED2="#57606a"
    ACCENT="#0969da"; GREEN="#1a7f37"; YELLOW="#9a6700"; RED="#cf222e"
    SS_BG="#dafbe1"; SS_BD="#1a7f37"; SS_TX="#116329"
    SN_BG="#fff8c5"; SN_BD="#9a6700"; SN_TX="#7d4e00"
    SW_BG="#ffebe9"; SW_BD="#cf222e"; SW_TX="#a40e26"
    SA_BG="#eaeef2"; SA_BD="#d0d7de"; SA_TX="#8c959f"
    AI_BG="#ddf4ff"; AI_BD="#0969da"; AI_TX="#0550ae"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html,body,[class*="css"]{{font-family:'IBM Plex Sans',sans-serif!important;background:{BG}!important;color:{TEXT}!important;}}
.block-container{{padding:1rem 1.5rem!important;max-width:1600px!important;}}
[data-testid="collapsedControl"]{{display:none;}}
.smm-header{{display:flex;align-items:center;justify-content:space-between;padding:10px 18px;background:{BG2};border:1px solid {BORDER};border-radius:10px;margin-bottom:14px;}}
.smm-title{{font-family:'IBM Plex Mono',monospace;font-size:1rem;font-weight:600;color:{ACCENT};letter-spacing:.04em;}}
.smm-subtitle{{font-size:.75rem;color:{MUTED};font-family:'IBM Plex Mono',monospace;}}
.smm-date{{font-family:'IBM Plex Mono',monospace;font-size:.72rem;color:{MUTED};}}
.stat-row{{display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap;}}
.stat-box{{background:{BG2};border:1px solid {BORDER};border-radius:8px;padding:8px 16px;min-width:110px;flex:1;}}
.stat-label{{font-size:.65rem;color:{MUTED};font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px;}}
.stat-value{{font-family:'IBM Plex Mono',monospace;font-size:1.15rem;font-weight:600;color:{TEXT2};}}
.stat-value.green{{color:{GREEN};}} .stat-value.yellow{{color:{YELLOW};}} .stat-value.blue{{color:{ACCENT};}}
.ticker-panel{{background:{BG2};border:1px solid {BORDER};border-radius:10px;padding:14px 16px;margin-top:8px;}}
.panel-header{{font-family:'IBM Plex Mono',monospace;font-size:.72rem;color:{MUTED};text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;border-bottom:1px solid {BORDER};padding-bottom:6px;}}
.score-bar-wrap{{margin:5px 0;}}
.score-bar-label{{display:flex;justify-content:space-between;font-family:'IBM Plex Mono',monospace;font-size:.68rem;color:{MUTED2};margin-bottom:2px;}}
.score-bar-track{{background:{BG3};border-radius:3px;height:5px;width:100%;overflow:hidden;}}
.score-bar-fill{{height:5px;border-radius:3px;}}
.signal-row{{display:flex;align-items:flex-start;gap:8px;padding:5px 0;border-bottom:1px solid {BG3};font-size:.78rem;}}
.signal-key{{font-family:'IBM Plex Mono',monospace;color:{MUTED};min-width:130px;font-size:.72rem;}}
.signal-val{{color:{TEXT};}}
.thesis-box{{background:{BG3};border-left:3px solid {ACCENT};border-radius:0 6px 6px 0;padding:8px 12px;font-size:.78rem;color:{MUTED2};margin-top:8px;font-style:italic;}}
.ai-box{{background:{AI_BG};border:1px solid {AI_BD};border-radius:8px;padding:12px 16px;margin-top:10px;font-size:.82rem;color:{AI_TX};line-height:1.6;}}
.ai-label{{font-family:'IBM Plex Mono',monospace;font-size:.65rem;color:{AI_BD};text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;}}
.ref-box{{background:{BG2};border:1px solid {BORDER};border-radius:8px;padding:10px 14px;margin-top:8px;font-size:.72rem;color:{MUTED};font-family:'IBM Plex Mono',monospace;line-height:1.9;}}
.company-name{{font-size:.72rem;color:{MUTED2};font-family:'IBM Plex Sans',sans-serif;margin-top:1px;}}
[data-testid="stDataFrame"]{{border:1px solid {BORDER}!important;border-radius:8px!important;}}
[data-baseweb="tab-list"]{{background:{BG2}!important;border-bottom:1px solid {BORDER}!important;gap:0!important;}}
[data-baseweb="tab"]{{font-family:'IBM Plex Mono',monospace!important;font-size:.78rem!important;color:{MUTED}!important;padding:8px 18px!important;}}
[aria-selected="true"][data-baseweb="tab"]{{color:{ACCENT}!important;border-bottom:2px solid {ACCENT}!important;}}
[data-testid="stMetric"]{{background:{BG2}!important;border:1px solid {BORDER}!important;border-radius:8px!important;padding:8px 12px!important;}}
[data-testid="stMetricLabel"]{{font-size:.65rem!important;color:{MUTED}!important;}}
[data-testid="stMetricValue"]{{font-size:1rem!important;font-family:'IBM Plex Mono',monospace!important;color:{TEXT2}!important;}}
.stButton>button{{background:{BG3}!important;border:1px solid {BORDER2}!important;color:{TEXT}!important;font-family:'IBM Plex Mono',monospace!important;font-size:.72rem!important;border-radius:6px!important;padding:4px 14px!important;}}
.stButton>button:hover{{border-color:{ACCENT}!important;color:{ACCENT}!important;}}
.stButton>button[kind="primary"]{{background:{SS_BG}!important;border-color:{SS_BD}!important;color:{SS_TX}!important;}}
[data-baseweb="select"]{{font-family:'IBM Plex Mono',monospace!important;font-size:.75rem!important;}}
.stTextInput input{{font-family:'IBM Plex Mono',monospace!important;font-size:.75rem!important;background:{BG2}!important;border:1px solid {BORDER2}!important;color:{TEXT}!important;}}
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────
def fmt_money(v):
    if v is None: return "—"
    try: v=float(v)
    except: return "—"
    if v==0: return "—"
    if abs(v)>=1e9: return f"${v/1e9:.1f}B"
    if abs(v)>=1e6: return f"${v/1e6:.1f}M"
    if abs(v)>=1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

def fmt_pct(v):
    if v is None: return "—"
    try: v=float(v)
    except: return "—"
    if v==0: return "—"
    if 0<abs(v)<1: return f"{v*100:.1f}%"
    return f"{v:.1f}%"

def fmt_price(v):
    if v is None: return "—"
    try: return f"${float(v):.2f}"
    except: return "—"

def fmt_ratio(v):
    if v is None: return "—"
    try: return f"{float(v):.2f}x"
    except: return "—"

def score_class(score):
    try: s=int(score)
    except: s=0
    if s>=70: return "green"
    if s>=45: return "yellow"
    return ""

def score_bar_html(label, value, max_val, color):
    pct=min(100,int((abs(value)/max_val)*100)) if max_val>0 else 0
    bar_color=RED if value<0 else color
    return (f'<div class="score-bar-wrap"><div class="score-bar-label"><span>{label}</span>'
            f'<span style="color:{bar_color}">{value:+d}</span></div>'
            f'<div class="score-bar-track"><div class="score-bar-fill" style="width:{pct}%;background:{bar_color}"></div>'
            f'</div></div>')

def signal_row_html(key, val):
    return (f'<div class="signal-row"><span class="signal-key">{key}</span>'
            f'<span class="signal-val">{val or "—"}</span></div>')

def safe_get(row, *keys):
    for k in keys:
        try:
            v=row[k]
            if v is not None and str(v).strip() not in ("","nan","None"):
                return str(v)
        except: pass
    return "—"


# ── AI Interpretation via Claude Haiku ────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_haiku_interpretation(ticker: str, data: dict) -> str:
    if not ANTHROPIC_KEY:
        return ""

    # Am eliminat punctul extra și am unit textul corect
    prompt = f"""Ești un analist financiar concis. Analizează aceste semnale pentru {ticker} și oferă o interpretare în 3 propoziții. Fii direct, specific și sincer în privința punctelor slabe.

Signals:
- Score: {data.get('score', 0)}/100
- Vol ratio: {data.get('vol_ratio', 0)}x vs 20d avg
- Insider buys (90d): {data.get('insider_buys_90d', 0)} transactions, value ${data.get('insider_buy_value', 0):,.0f}
- Insider sells (90d): {data.get('insider_sells_90d', 0)} transactions
- Top insider role: {data.get('top_insider_role', 'Unknown')}
- Short interest: {data.get('short_interest_pct', 0)}%
- Institutional ownership: {data.get('inst_ownership_pct', '—')}%
- P/E ratio: {data.get('pe_ratio', '—')}
- Market cap: ${data.get('market_cap', 0)/1e6:.0f}M
- Sector: {data.get('sector', '—')}
- Ownership form (13D/13G): {data.get('ownership_form', '—')}

Scrie 3 propoziții: (1) ce sugerează combinația dintre volum și activitatea insiderilor, (2) ce aspecte ridică semne de întrebare sau confirmă teza, (3) un risc sau o avertizare specifică. Fără umplutură."""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-haiku-20240307", # Model corectat
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        return f"AI unavailable: {e}"


# ── Data loaders ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_scanner(days_back, min_score):
    try: return get_enriched(days_back=days_back, min_score=min_score)
    except Exception as e: st.error(f"DB error: {e}"); return []

@st.cache_data(ttl=300)
def load_watchlist_data():
    try: return get_watchlist(), get_watchlist_enriched()
    except Exception as e: st.error(f"DB error: {e}"); return [], []

@st.cache_data(ttl=120)
def load_history(ticker):
    return get_ticker_history(ticker, limit=10)


# ── DataFrame builder ──────────────────────────────────────────────────────────
def build_df(rows):
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows).copy()
    needed = ["ticker","company_name","score","price","vol_ratio","volume","avg_volume_20d",
              "insider_buys_90d","insider_buy_value","insider_sells_90d",
              "short_interest_pct","short_sale_ratio","pe_ratio","market_cap",
              "sector","top_insider_role","ownership_form","enrich_date"]
    for c in needed:
        if c not in df.columns: df[c] = None
    df["score"]          = df["score"].fillna(0).astype(int)
    df["company_name"]   = df["company_name"].fillna("").astype(str)
    df["Display Price"]  = df["price"].apply(fmt_price)
    df["Vol Ratio"]      = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["Buys 90d"]       = df["insider_buys_90d"].fillna(0).astype(int)
    df["Buy Value"]      = df["insider_buy_value"].apply(fmt_money)
    df["Sells 90d"]      = df["insider_sells_90d"].fillna(0).astype(int)
    df["Short %"]        = df["short_interest_pct"].apply(fmt_pct)
    df["Short Flow"]     = df["short_sale_ratio"].apply(fmt_pct)
    df["P/E"]            = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    df["Mkt Cap"]        = df["market_cap"].apply(fmt_money)
    df["Date"]           = df["enrich_date"]
    return df


# ── Ticker detail panel ────────────────────────────────────────────────────────
def render_ticker_panel(ticker: str):
    history = load_history(ticker)
    if not history:
        st.info("Nu există istoric pentru acest ticker.")
        return

    latest     = history[-1]
    prev       = history[-2] if len(history) >= 2 else None
    score_delta = int(latest.get("score",0)) - int(prev.get("score",0) if prev else 0)

    st.markdown(f'<div class="panel-header">📊 {ticker} · Intelligence Panel</div>', unsafe_allow_html=True)

    # Company name sub ticker
    company = latest.get("company_name") or ""
    if company and company not in ("", "nan", "None"):
        st.markdown(f'<div class="company-name">{company}</div>', unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Score", latest.get("score",0), delta=score_delta)
    c2.metric("Price", fmt_price(latest.get("price")))
    c3.metric("Vol Ratio", fmt_ratio(latest.get("vol_ratio")))
    c4.metric("Short Interest", fmt_pct(latest.get("short_interest_pct")))
    c5.metric("Mkt Cap", fmt_money(latest.get("market_cap")))

    left, mid, right = st.columns([1.8, 1.4, 1.4])

    with left:
        st.markdown("**Score Breakdown**")
        sv = int(latest.get("score_volume") or 0)
        si = int(latest.get("score_insider") or 0)
        sq = int(latest.get("score_insider_quality") or 0)
        so = int(latest.get("score_ownership") or 0)
        ss = int(latest.get("score_short_interest") or 0)
        sf = int(latest.get("score_short_flow") or 0)
        sp = int(latest.get("score_penalty") or 0)
        bars = (score_bar_html("Volume", sv, 25, ACCENT) +
                score_bar_html("Insider qty", si, 35, GREEN) +
                score_bar_html("Insider quality", sq, 20, GREEN) +
                score_bar_html("Ownership", so, 15, ACCENT) +
                score_bar_html("Short interest", ss, 10, YELLOW) +
                score_bar_html("Short flow", sf, 10, YELLOW) +
                score_bar_html("Penalty", sp, 15, RED))
        st.markdown(f'<div class="ticker-panel">{bars}</div>', unsafe_allow_html=True)

        if len(history) > 1:
            hist_df = pd.DataFrame(history)
            chart_df = hist_df[["enrich_date","score"]].copy()
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
            unsafe_allow_html=True,
        )

        # ── Claude Haiku interpretation ──────────────────────────────────────
        if ANTHROPIC_KEY:
            with st.spinner("AI analizează..."):
                interp = get_haiku_interpretation(ticker, latest)
            if interp and not interp.startswith("AI unavailable"):
                st.markdown(
                    f'<div class="ai-box"><div class="ai-label">Claude Haiku · interpretare</div>{interp}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f'<div class="ai-box"><div class="ai-label">Claude Haiku · interpretare</div>'
                f'Adaugă ANTHROPIC_API_KEY în Streamlit Secrets pentru interpretări AI.</div>',
                unsafe_allow_html=True,
            )

    with right:
        st.markdown("**Istoric (10 zile)**")
        hist_df = pd.DataFrame(history)
        show_cols = ["enrich_date","score","vol_ratio","insider_buys_90d","insider_buy_value","short_interest_pct"]
        for c in show_cols:
            if c not in hist_df.columns: hist_df[c] = None
        h = hist_df[show_cols].copy()
        h["vol_ratio"]           = h["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
        h["insider_buy_value"]   = h["insider_buy_value"].apply(fmt_money)
        h["short_interest_pct"]  = h["short_interest_pct"].apply(fmt_pct)
        h.columns = ["Date","Score","Vol","Buys","Buy$","SI%"]
        st.dataframe(h, hide_index=True, use_container_width=True, height=220)
        st.markdown(
            f'<div class="ref-box">Score ≥70 → strong<br>Vol ≥5x → extreme<br>'
            f'SI &lt;5% → low pressure<br>13D &gt; 13G<br>'
            f'CEO/CFO &gt; Director<br>Short flow &gt;60% → presiune</div>',
            unsafe_allow_html=True,
        )


# ── Header ─────────────────────────────────────────────────────────────────────
h1, h2 = st.columns([10, 1])
with h1:
    st.markdown(f"""
<div class="smm-header">
  <div>
    <div class="smm-title">📡 SMART MONEY SCREENER</div>
    <div class="smm-subtitle">volume spikes · insider activity · short flows · ownership signals</div>
  </div>
  <div class="smm-date">{date.today().strftime('%d %b %Y')}</div>
</div>
""", unsafe_allow_html=True)
with h2:
    st.write("")
    if st.button("☀️ Light" if dark else "🌙 Dark", key="theme_btn"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_scan, tab_watch = st.tabs(["Scanner", "Watchlist"])


# ══ SCANNER ════════════════════════════════════════════════════════════════════
with tab_scan:
    fc1,fc2,fc3,fc4,_ = st.columns([1,1,1.2,1.5,3])
    with fc1: min_score = st.slider("Score min", 0, 100, 30, 5)
    with fc2: days_back = st.selectbox("Perioadă", [1,2,3,5,10], format_func=lambda x: f"{x}d")
    with fc3: sector_filter = st.text_input("Sector", placeholder="ex: Technology")
    with fc4: search_ticker = st.text_input("Ticker search", placeholder="ex: NVDA").upper().strip()

    raw     = load_scanner(days_back, min_score)
    df_full = build_df(raw)
    df      = df_full.copy()

    if not df.empty:
        if search_ticker:
            df = df[df["ticker"].str.contains(search_ticker, case=False, na=False)]
        if sector_filter:
            df = df[df["sector"].str.contains(sector_filter, case=False, na=False)]

    if not df.empty:
        total=len(df); avg_s=int(df["score"].mean())
        top_t=df.nlargest(1,"score").iloc[0]["ticker"]; top_s=int(df["score"].max())
        strong=int((df["score"]>=70).sum()); neutral=int(((df["score"]>=45)&(df["score"]<70)).sum()); weak=int((df["score"]<45).sum())

        st.markdown(f"""
<div class="stat-row">
  <div class="stat-box"><div class="stat-label">Candidates</div><div class="stat-value blue">{total}</div></div>
  <div class="stat-box"><div class="stat-label">Avg Score</div><div class="stat-value">{avg_s}</div></div>
  <div class="stat-box"><div class="stat-label">Top Ticker</div><div class="stat-value blue">{top_t}</div></div>
  <div class="stat-box"><div class="stat-label">Top Score</div><div class="stat-value {score_class(top_s)}">{top_s}</div></div>
  <div class="stat-box"><div class="stat-label">▲ Strong ≥70</div><div class="stat-value green">{strong}</div></div>
  <div class="stat-box"><div class="stat-label">◆ Neutral 45–70</div><div class="stat-value yellow">{neutral}</div></div>
  <div class="stat-box"><div class="stat-label">▼ Weak &lt;45</div><div class="stat-value">{weak}</div></div>
</div>
""", unsafe_allow_html=True)

        # Tabel cu company name
        display_df = df[[
            "ticker","company_name","score","Display Price","Vol Ratio",
            "Buys 90d","Buy Value","Sells 90d","Short %",
            "top_insider_role","P/E","Mkt Cap","sector","Date",
        ]].rename(columns={
            "ticker":"Ticker","company_name":"Company","score":"Score",
            "Display Price":"Price","top_insider_role":"Role","sector":"Sector",
        })

        st.dataframe(
            display_df, hide_index=True, use_container_width=True, height=320,
            column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")},
        )

        ac1,ac2,ac3,ac4 = st.columns([2,1.2,1.2,5])
        with ac1:
            selected_ticker = st.selectbox("Selectează ticker", df["ticker"].tolist(), key="scan_sel", label_visibility="collapsed")
        with ac2:
            if st.button("➕ Add to watchlist", type="primary"):
                add_to_watchlist(selected_ticker)
                st.success(f"{selected_ticker} adăugat.")
                st.cache_data.clear(); st.rerun()
        with ac3:
            if st.button("🔄 Refresh"):
                st.cache_data.clear(); st.rerun()
        with ac4:
            row = df[df["ticker"]==selected_ticker].iloc[0]
            role = safe_get(row, "top_insider_role")
            vol_r = safe_get(row, "Vol Ratio")
            company_short = safe_get(row, "company_name")
            st.markdown(
                f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:.72rem;color:{MUTED};padding-top:8px">'
                f'{selected_ticker} · <span style="color:{MUTED2}">{company_short[:30]}</span> · '
                f'score <b style="color:{TEXT2}">{row["score"]}</b> · {vol_r} vol · {role}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")
        render_ticker_panel(selected_ticker)
    else:
        st.info("Niciun candidat pentru filtrele curente.")


# ══ WATCHLIST ══════════════════════════════════════════════════════════════════
with tab_watch:
    wc1,wc2,wc3,_ = st.columns([1.5,3,1.5,4])
    with wc1: new_ticker = st.text_input("Ticker", placeholder="ex: NVDA", key="wl_ticker")
    with wc2: notes = st.text_input("Notes", placeholder="setup, motiv, context", key="wl_notes")
    with wc3:
        st.write(""); st.write("")
        if st.button("➕ Add", type="primary"):
            t=(new_ticker or "").upper().strip()
            if t:
                add_to_watchlist(t, notes)
                st.success(f"{t} adăugat.")
                st.cache_data.clear(); st.rerun()
            else: st.warning("Ticker invalid.")

    wl_raw, wl_enriched = load_watchlist_data()
    df_w_full = build_df(wl_enriched)

    if not wl_raw:
        st.info("Watchlist gol. Adaugă tickers din Scanner sau manual.")
    else:
        total_w=len(wl_raw); covered=len(df_w_full["ticker"].unique()) if not df_w_full.empty else 0
        all_t=set(w["ticker"] for w in wl_raw)
        have_t=set(df_w_full["ticker"].tolist()) if not df_w_full.empty else set()
        missing_set=all_t-have_t

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
                "ticker","company_name","score","Display Price","Vol Ratio",
                "Buys 90d","Buy Value","Sells 90d","Short %",
                "top_insider_role","P/E","sector","Date",
            ]].rename(columns={
                "ticker":"Ticker","company_name":"Company","score":"Score",
                "Display Price":"Price","top_insider_role":"Role","sector":"Sector",
            })

            st.dataframe(
                display_w, hide_index=True, use_container_width=True, height=280,
                column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")},
            )

            wac1,wac2,wac3,wac4 = st.columns([2,1.2,1.2,5])
            with wac1:
                selected_w = st.selectbox("Selectează", df_w_full["ticker"].tolist(), key="wl_sel", label_visibility="collapsed")
            with wac2:
                if st.button("🗑 Remove"):
                    remove_from_watchlist(selected_w)
                    st.success(f"{selected_w} șters.")
                    st.cache_data.clear(); st.rerun()
            with wac3:
                if st.button("🔄 Reload"):
                    st.cache_data.clear(); st.rerun()
            with wac4:
                row_w = df_w_full[df_w_full["ticker"]==selected_w].iloc[0]
                role_w = safe_get(row_w, "top_insider_role")
                vol_rw = safe_get(row_w, "Vol Ratio")
                company_w = safe_get(row_w, "company_name")
                st.markdown(
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:.72rem;color:{MUTED};padding-top:8px">'
                    f'{selected_w} · <span style="color:{MUTED2}">{company_w[:30]}</span> · '
                    f'score <b style="color:{TEXT2}">{row_w["score"]}</b> · {vol_rw} vol · {role_w}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            render_ticker_panel(selected_w)
