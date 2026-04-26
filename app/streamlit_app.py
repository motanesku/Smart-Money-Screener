"""
Smart Money Screener v8
- Light mode only
- Layout configurabil (drag panels, resize, reorder)
- Company name în tabel și detaliu
- Claude Haiku interpretare
"""
import sys, os, requests
sys.path.insert(0, ".")
from datetime import date
import pandas as pd
import streamlit as st
from app.db import (
    get_enriched, get_watchlist, get_watchlist_enriched,
    get_ticker_history, add_to_watchlist, remove_from_watchlist,
)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

st.set_page_config(page_title="Smart Money Screener", page_icon="📡",
                   layout="wide", initial_sidebar_state="collapsed")

# ── Palette light ──────────────────────────────────────────────────────────────
BG="#f6f8fa"; BG2="#ffffff"; BG3="#eaeef2"
BORDER="#d0d7de"; BORDER2="#b0bec5"
TEXT="#1c1f23"; TEXT2="#0d1117"
MUTED="#8c959f"; MUTED2="#57606a"
ACCENT="#0969da"; GREEN="#1a7f37"; YELLOW="#9a6700"; RED="#cf222e"
AI_BG="#ddf4ff"; AI_BD="#0969da"; AI_TX="#0550ae"

st.markdown(f"""<style>
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
.company-sub{{font-size:.78rem;color:{MUTED2};margin-bottom:10px;}}
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
.layout-config{{background:{BG3};border:1px solid {BORDER};border-radius:8px;padding:12px 16px;margin-bottom:14px;}}
.layout-config h4{{font-family:'IBM Plex Mono',monospace;font-size:.75rem;color:{MUTED};margin:0 0 10px 0;text-transform:uppercase;letter-spacing:.06em;}}
[data-testid="stDataFrame"]{{border:1px solid {BORDER}!important;border-radius:8px!important;}}
[data-baseweb="tab-list"]{{background:{BG2}!important;border-bottom:1px solid {BORDER}!important;}}
[data-baseweb="tab"]{{font-family:'IBM Plex Mono',monospace!important;font-size:.78rem!important;color:{MUTED}!important;padding:8px 18px!important;}}
[aria-selected="true"][data-baseweb="tab"]{{color:{ACCENT}!important;border-bottom:2px solid {ACCENT}!important;}}
[data-testid="stMetric"]{{background:{BG2}!important;border:1px solid {BORDER}!important;border-radius:8px!important;padding:8px 12px!important;}}
[data-testid="stMetricLabel"]{{font-size:.65rem!important;color:{MUTED}!important;}}
[data-testid="stMetricValue"]{{font-size:1rem!important;font-family:'IBM Plex Mono',monospace!important;color:{TEXT2}!important;}}
.stButton>button{{background:{BG3}!important;border:1px solid {BORDER2}!important;color:{TEXT}!important;font-family:'IBM Plex Mono',monospace!important;font-size:.72rem!important;border-radius:6px!important;padding:4px 14px!important;}}
.stButton>button:hover{{border-color:{ACCENT}!important;color:{ACCENT}!important;}}
.stButton>button[kind="primary"]{{background:#dafbe1!important;border-color:#1a7f37!important;color:#116329!important;}}
.stTextInput input{{font-family:'IBM Plex Mono',monospace!important;font-size:.75rem!important;background:{BG2}!important;border:1px solid {BORDER2}!important;color:{TEXT}!important;}}
</style>""", unsafe_allow_html=True)


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
def fmt_int(v):
    if v is None or v==0: return "—"
    try: return f"{int(v):,}"
    except: return "—"
def score_class(s):
    try: s=int(s)
    except: s=0
    return "green" if s>=70 else ("yellow" if s>=45 else "")
def sbar(label, value, max_val, color):
    pct=min(100,int((abs(value)/max_val)*100)) if max_val>0 else 0
    c=RED if value<0 else color
    return (f'<div class="score-bar-wrap"><div class="score-bar-label">'
            f'<span>{label}</span><span style="color:{c}">{value:+d}</span></div>'
            f'<div class="score-bar-track"><div class="score-bar-fill" style="width:{pct}%;background:{c}"></div>'
            f'</div></div>')
def srow(key, val):
    return (f'<div class="signal-row"><span class="signal-key">{key}</span>'
            f'<span class="signal-val">{val or "—"}</span></div>')
def safe(row, *keys):
    for k in keys:
        try:
            v=row[k]
            if v is not None and str(v).strip() not in ("","nan","None"): return str(v)
        except: pass
    return "—"


# ── Layout config in session state ────────────────────────────────────────────
PANEL_OPTIONS = ["Score Breakdown", "Semnale + AI", "Istoric", "Chart scor"]
DEFAULT_PANELS = ["Score Breakdown", "Semnale + AI", "Istoric"]
COL_OPTIONS = ["Ticker","Company","Score","Price","Vol Ratio","Volume",
               "Buys 90d","Buy Value","Sells 90d","Short %","Short Flow",
               "Role","P/E","Mkt Cap","Sector","Form","Date"]
DEFAULT_COLS = ["Ticker","Company","Score","Price","Vol Ratio",
                "Buys 90d","Buy Value","Short %","Role","Mkt Cap","Sector","Date"]

if "layout_panels" not in st.session_state:
    st.session_state.layout_panels = list(DEFAULT_PANELS)
if "layout_cols" not in st.session_state:
    st.session_state.layout_cols = list(DEFAULT_COLS)
if "detail_width" not in st.session_state:
    st.session_state.detail_width = [1.8, 1.4, 1.4]
if "show_layout" not in st.session_state:
    st.session_state.show_layout = False


# ── AI Haiku ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_haiku(ticker: str, score: int, vol: float, buys: int, buy_val: float,
              sells: int, sell_val: float, role: str, si: float, sf: float,
              sector: str, mc: int, ownership_form: str) -> str:
    if not ANTHROPIC_KEY:
        return ""

    # Construiește contextul pentru scor nou (fără insider în scor)
    score_context = []
    if vol >= 2:    score_context.append(f"volum {vol}x față de medie (semnal principal)")
    if sf >= 0.5:   score_context.append(f"short flow {sf*100:.0f}% din volum total")
    if si >= 10:    score_context.append(f"short interest {si:.1f}% — potențial squeeze")
    if ownership_form: score_context.append(f"filing {ownership_form} recent")
    if buys > 0:    score_context.append(f"{buys} cumpărări insider în 90 zile (${buy_val:,.0f}) — context")
    if sells > 0:   score_context.append(f"{sells} vânzări insider în 90 zile (${sell_val:,.0f}) — monitorizează")

    prompt = (
        f"Ești un analist financiar concis care scrie în română. "
        f"Analizează semnalele smart money pentru {ticker} ({sector}, cap ${mc/1e6:.0f}M). "
        f"Scor: {score}/100. "
        f"Semnale: {'; '.join(score_context) if score_context else 'niciun semnal semnificativ'}. "
        f"Scrie exact 3 propoziții în română: "
        f"(1) ce sugerează pattern-ul de volum și presiune, "
        f"(2) ce confirmă sau contrazice teza, "
        f"(3) un risc specific. "
        f"Fii direct, concret, fără introduceri."
    )

    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 250,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=15)
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        return f"AI indisponibil: {e}"


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
    df["score"]         = df["score"].fillna(0).astype(int)
    df["company_name"]  = df["company_name"].fillna("").astype(str)
    # Coloane display
    df["Company"]       = df["company_name"].apply(lambda x: x[:28] if x else "—")
    df["Price"]         = df["price"].apply(fmt_price)
    df["Vol Ratio"]     = df["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
    df["Volume"]        = df["volume"].apply(fmt_int)
    df["Buys 90d"]      = df["insider_buys_90d"].fillna(0).astype(int)
    df["Buy Value"]     = df["insider_buy_value"].apply(fmt_money)
    df["Sells 90d"]     = df["insider_sells_90d"].fillna(0).astype(int)
    df["Short %"]       = df["short_interest_pct"].apply(fmt_pct)
    df["Short Flow"]    = df["short_sale_ratio"].apply(fmt_pct)
    df["P/E"]           = df["pe_ratio"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    df["Mkt Cap"]       = df["market_cap"].apply(fmt_money)
    df["Role"]          = df["top_insider_role"].fillna("—")
    df["Form"]          = df["ownership_form"].fillna("—")
    df["Sector"]        = df["sector"].fillna("—")
    df["Date"]          = df["enrich_date"]
    return df


# ── Detail panel ───────────────────────────────────────────────────────────────
def render_detail(ticker: str):
    history = load_history(ticker)
    if not history:
        st.info("Nu există date pentru acest ticker.")
        return
    latest     = history[-1]
    prev       = history[-2] if len(history) >= 2 else None
    score_delta = int(latest.get("score",0)) - int(prev.get("score",0) if prev else 0)

    st.markdown(f'<div class="panel-header">📊 {ticker} · Intelligence Panel</div>', unsafe_allow_html=True)
    company = str(latest.get("company_name") or "")
    if company and company not in ("", "nan", "None"):
        st.markdown(f'<div class="company-sub">{company}</div>', unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Score", latest.get("score",0), delta=score_delta)
    c2.metric("Price", fmt_price(latest.get("price")))
    c3.metric("Vol Ratio", fmt_ratio(latest.get("vol_ratio")))
    c4.metric("Short Int", fmt_pct(latest.get("short_interest_pct")))
    c5.metric("Mkt Cap", fmt_money(latest.get("market_cap")))

    panels = st.session_state.layout_panels
    widths = st.session_state.detail_width
    n = len(panels)
    if n == 0: return
    w = widths[:n] if len(widths) >= n else ([1.5]*n)
    cols = st.columns(w)

    for idx, panel in enumerate(panels):
        with cols[idx]:
            if panel == "Score Breakdown":
                st.markdown("**Score Breakdown**")
                bars = (sbar("Volume",          int(latest.get("score_volume") or 0),          25, ACCENT) +
                        sbar("Insider qty",      int(latest.get("score_insider") or 0),         35, GREEN) +
                        sbar("Insider quality",  int(latest.get("score_insider_quality") or 0), 20, GREEN) +
                        sbar("Ownership",        int(latest.get("score_ownership") or 0),       15, ACCENT) +
                        sbar("Short interest",   int(latest.get("score_short_interest") or 0),  10, YELLOW) +
                        sbar("Short flow",       int(latest.get("score_short_flow") or 0),      10, YELLOW) +
                        sbar("Penalty",          int(latest.get("score_penalty") or 0),         15, RED))
                st.markdown(f'<div class="ticker-panel">{bars}</div>', unsafe_allow_html=True)

            elif panel == "Semnale + AI":
                st.markdown("**Semnale**")
                sigs = (srow("Volume",        latest.get("volume_signal")) +
                        srow("Insider",       latest.get("insider_signal")) +
                        srow("Insider role",  latest.get("top_insider_role")) +
                        srow("Ownership",     latest.get("ownership_signal")) +
                        srow("Own. form",     latest.get("ownership_form")) +
                        srow("Own. pct",      fmt_pct(latest.get("ownership_pct"))) +
                        srow("Short int",     latest.get("short_signal")) +
                        srow("Short flow",    latest.get("short_flow_signal")))
                thesis = latest.get("thesis") or ""
                st.markdown(f'<div class="ticker-panel">{sigs}<div class="thesis-box">{thesis}</div></div>',
                            unsafe_allow_html=True)
                if ANTHROPIC_KEY:
                    with st.spinner("AI analizează..."):
                        interp = get_haiku(
                            ticker,
                            int(latest.get("score", 0)),
                            float(latest.get("vol_ratio") or 0),
                            int(latest.get("insider_buys_90d") or 0),
                            float(latest.get("insider_buy_value") or 0),
                            int(latest.get("insider_sells_90d") or 0),
                            float(latest.get("insider_sell_value") or 0),
                            str(latest.get("top_insider_role") or "Unknown"),
                            float(latest.get("short_interest_pct") or 0),
                            float(latest.get("short_sale_ratio") or 0),
                            str(latest.get("sector") or "—"),
                            int(latest.get("market_cap") or 0),
                            str(latest.get("ownership_form") or ""),
                        )
                    if interp and not interp.startswith("AI indisponibil"):
                        st.markdown(f'<div class="ai-box"><div class="ai-label">🤖 Claude Haiku · Interpretare</div>{interp}</div>',
                                    unsafe_allow_html=True)
                else:
                    st.caption("Adaugă ANTHROPIC_API_KEY în Secrets pentru interpretare AI.")

            elif panel == "Istoric":
                st.markdown("**Istoric (10 zile)**")
                hist_df = pd.DataFrame(history)
                cols_show = ["enrich_date","score","vol_ratio","insider_buys_90d",
                             "insider_buy_value","short_interest_pct"]
                for c in cols_show:
                    if c not in hist_df.columns: hist_df[c] = None
                h = hist_df[cols_show].copy()
                h["vol_ratio"]          = h["vol_ratio"].apply(lambda x: f"{float(x):.2f}x" if pd.notna(x) else "—")
                h["insider_buy_value"]  = h["insider_buy_value"].apply(fmt_money)
                h["short_interest_pct"] = h["short_interest_pct"].apply(fmt_pct)
                h.columns = ["Date","Score","Vol","Buys","Buy$","SI%"]
                st.dataframe(h, hide_index=True, use_container_width=True, height=220)
                st.markdown(f'<div class="ref-box">Score ≥70 → strong<br>Vol ≥5x → extreme<br>'
                            f'SI &lt;5% → low pressure<br>13D &gt; 13G<br>'
                            f'CEO/CFO &gt; Director</div>', unsafe_allow_html=True)

            elif panel == "Chart scor":
                st.markdown("**Evoluție scor**")
                if len(history) > 1:
                    hist_df = pd.DataFrame(history)
                    c_df = hist_df[["enrich_date","score"]].copy()
                    c_df["enrich_date"] = pd.to_datetime(c_df["enrich_date"])
                    c_df = c_df.set_index("enrich_date")
                    st.line_chart(c_df, height=200, use_container_width=True)
                else:
                    st.info("Nevoie de cel puțin 2 zile de date.")


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f"""<div style="margin:-1rem -1rem 1rem -1rem;padding:12px 18px;background:{BG2};border-bottom:1px solid {BORDER};">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:1rem;font-weight:600;color:{ACCENT};letter-spacing:.04em;margin-bottom:4px;">
        📡 SMART MONEY SCREENER
      </div>
      <div style="font-size:.72rem;color:{MUTED};font-family:'IBM Plex Mono',monospace;margin-bottom:4px;">
        volume spikes · insider activity · short flows · ownership signals
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:.72rem;color:{MUTED};margin-bottom:8px;">
        {date.today().strftime('%d %b %Y')}
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# Layout button
col1, col2, col3 = st.columns([10, 1, 0.5])
with col3:
    if st.button("⚙️", key="layout_btn", help="Configurare layout"):
        st.session_state.show_layout = not st.session_state.show_layout
        st.rerun()


# ── Layout configurator ────────────────────────────────────────────────────────
if st.session_state.show_layout:
    st.markdown('<div class="layout-config"><h4>⚙️ Configurare layout</h4></div>',
                unsafe_allow_html=True)
    lc1, lc2, lc3 = st.columns(3)

    with lc1:
        st.markdown("**Coloane tabel** (ordine = ordine afișare)")
        new_cols = st.multiselect("Coloane vizibile", COL_OPTIONS,
                                  default=st.session_state.layout_cols,
                                  key="col_picker")
        # Reorder cu up/down
        if new_cols != st.session_state.layout_cols:
            st.session_state.layout_cols = new_cols

    with lc2:
        st.markdown("**Panouri detaliu** (ordine = stânga → dreapta)")
        new_panels = st.multiselect("Panouri active", PANEL_OPTIONS,
                                    default=st.session_state.layout_panels,
                                    key="panel_picker")
        if new_panels != st.session_state.layout_panels:
            st.session_state.layout_panels = new_panels
            st.rerun()

    with lc3:
        st.markdown("**Lățime panouri** (raport relativ)")
        n = len(st.session_state.layout_panels)
        new_widths = []
        for i, pname in enumerate(st.session_state.layout_panels):
            cur = st.session_state.detail_width[i] if i < len(st.session_state.detail_width) else 1.5
            w   = st.slider(f"{pname[:15]}", 0.5, 3.0, float(cur), 0.1, key=f"w_{i}")
            new_widths.append(w)
        if new_widths != st.session_state.detail_width:
            st.session_state.detail_width = new_widths

    rc1, rc2 = st.columns([1, 8])
    with rc1:
        if st.button("Reset layout"):
            st.session_state.layout_panels = list(DEFAULT_PANELS)
            st.session_state.layout_cols   = list(DEFAULT_COLS)
            st.session_state.detail_width  = [1.8, 1.4, 1.4]
            st.rerun()
    st.markdown("---")


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_scan, tab_watch = st.tabs(["Scanner", "Watchlist"])


# ══ SCANNER ════════════════════════════════════════════════════════════════════
with tab_scan:
    fc1,fc2,fc3,fc4,_ = st.columns([1,1,1.2,1.5,3])
    with fc1: min_score  = st.slider("Score min", 0, 100, 30, 5)
    with fc2: days_back  = st.selectbox("Perioadă", [1,2,3,5,10], format_func=lambda x: f"{x}d")
    with fc3: sec_filter = st.text_input("Sector", placeholder="ex: Technology")
    with fc4: tck_search = st.text_input("Ticker", placeholder="ex: NVDA").upper().strip()

    raw     = load_scanner(days_back, min_score)
    df_full = build_df(raw)
    df      = df_full.copy()

    if not df.empty:
        if tck_search: df = df[df["ticker"].str.contains(tck_search, case=False, na=False)]
        if sec_filter: df = df[df["sector"].str.contains(sec_filter, case=False, na=False)]

    if not df.empty:
        total=len(df); avg_s=int(df["score"].mean())
        top_t=df.nlargest(1,"score").iloc[0]["ticker"]; top_s=int(df["score"].max())
        strong=int((df["score"]>=70).sum()); neutral=int(((df["score"]>=45)&(df["score"]<70)).sum()); weak=int((df["score"]<45).sum())

        st.markdown(f"""<div class="stat-row">
  <div class="stat-box"><div class="stat-label">Candidates</div><div class="stat-value blue">{total}</div></div>
  <div class="stat-box"><div class="stat-label">Avg Score</div><div class="stat-value">{avg_s}</div></div>
  <div class="stat-box"><div class="stat-label">Top Ticker</div><div class="stat-value blue">{top_t}</div></div>
  <div class="stat-box"><div class="stat-label">Top Score</div><div class="stat-value {score_class(top_s)}">{top_s}</div></div>
  <div class="stat-box"><div class="stat-label">▲ Strong ≥70</div><div class="stat-value green">{strong}</div></div>
  <div class="stat-box"><div class="stat-label">◆ Neutral 45–70</div><div class="stat-value yellow">{neutral}</div></div>
  <div class="stat-box"><div class="stat-label">▼ Weak &lt;45</div><div class="stat-value">{weak}</div></div>
</div>""", unsafe_allow_html=True)

        # Aplică coloanele configurate de user
        active_cols = st.session_state.layout_cols
        col_map     = {"Ticker":"ticker","Company":"Company","Score":"score",
                       "Price":"Price","Vol Ratio":"Vol Ratio","Volume":"Volume",
                       "Buys 90d":"Buys 90d","Buy Value":"Buy Value","Sells 90d":"Sells 90d",
                       "Short %":"Short %","Short Flow":"Short Flow","Role":"Role",
                       "P/E":"P/E","Mkt Cap":"Mkt Cap","Sector":"Sector","Form":"Form","Date":"Date"}
        disp_cols   = [col_map[c] for c in active_cols if col_map.get(c) in df.columns]
        disp_df     = df[disp_cols].rename(columns={"ticker":"Ticker","score":"Score"})

        st.dataframe(disp_df, hide_index=True, use_container_width=True, height=320,
            column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")})

        ac1,ac2,ac3,ac4 = st.columns([2,1.2,1.2,5])
        with ac1:
            sel = st.selectbox("Ticker", df["ticker"].tolist(), key="scan_sel", label_visibility="collapsed")
        with ac2:
            if st.button("➕ Add to watchlist", type="primary"):
                add_to_watchlist(sel)
                st.success(f"{sel} adăugat.")
                st.cache_data.clear(); st.rerun()
        with ac3:
            if st.button("🔄 Refresh"):
                st.cache_data.clear(); st.rerun()
        with ac4:
            row    = df[df["ticker"]==sel].iloc[0]
            comp   = safe(row, "Company","company_name")
            vol_r  = safe(row, "Vol Ratio")
            role   = safe(row, "Role","top_insider_role")
            st.markdown(f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:.72rem;'
                        f'color:{MUTED};padding-top:8px">{sel} · <span style="color:{MUTED2}">'
                        f'{comp[:35]}</span> · score <b style="color:{TEXT2}">{row["score"]}</b>'
                        f' · {vol_r} · {role}</div>', unsafe_allow_html=True)

        st.markdown("---")
        render_detail(sel)
    else:
        st.info("Niciun candidat. Datele se actualizează la 08:45 ET și 16:30 ET.")


# ══ WATCHLIST ══════════════════════════════════════════════════════════════════
with tab_watch:
    wc1,wc2,wc3,_ = st.columns([1.5,3,1.5,4])
    with wc1: new_t  = st.text_input("Ticker", placeholder="ex: NVDA", key="wl_ticker")
    with wc2: notes  = st.text_input("Notes", placeholder="setup, motiv, context", key="wl_notes")
    with wc3:
        st.write(""); st.write("")
        if st.button("➕ Add", type="primary"):
            t=(new_t or "").upper().strip()
            if t: add_to_watchlist(t, notes); st.success(f"{t} adăugat."); st.cache_data.clear(); st.rerun()
            else: st.warning("Ticker invalid.")

    wl_raw, wl_enriched = load_watchlist_data()
    df_w = build_df(wl_enriched)

    if not wl_raw:
        st.info("Watchlist gol.")
    else:
        total_w=len(wl_raw); covered=len(df_w["ticker"].unique()) if not df_w.empty else 0
        all_t=set(w["ticker"] for w in wl_raw)
        have_t=set(df_w["ticker"].tolist()) if not df_w.empty else set()
        miss=all_t-have_t

        st.markdown(f"""<div class="stat-row">
  <div class="stat-box"><div class="stat-label">Watchlist</div><div class="stat-value blue">{total_w}</div></div>
  <div class="stat-box"><div class="stat-label">Cu date</div><div class="stat-value green">{covered}</div></div>
  <div class="stat-box"><div class="stat-label">Fără date</div><div class="stat-value">{len(miss)}</div></div>
</div>""", unsafe_allow_html=True)

        if miss:
            st.warning("Fără date enrich: " + ", ".join(sorted(miss)))

        if not df_w.empty:
            active_cols_w = [c for c in st.session_state.layout_cols if c != "Date"] + ["Date"]
            col_map_w     = {"Ticker":"ticker","Company":"Company","Score":"score",
                             "Price":"Price","Vol Ratio":"Vol Ratio","Volume":"Volume",
                             "Buys 90d":"Buys 90d","Buy Value":"Buy Value","Sells 90d":"Sells 90d",
                             "Short %":"Short %","Short Flow":"Short Flow","Role":"Role",
                             "P/E":"P/E","Mkt Cap":"Mkt Cap","Sector":"Sector","Form":"Form","Date":"Date"}
            disp_w   = [col_map_w[c] for c in active_cols_w if col_map_w.get(c) in df_w.columns]
            disp_df_w = df_w[disp_w].rename(columns={"ticker":"Ticker","score":"Score"})

            st.dataframe(disp_df_w, hide_index=True, use_container_width=True, height=280,
                column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")})

            wac1,wac2,wac3,wac4 = st.columns([2,1.2,1.2,5])
            with wac1:
                sel_w = st.selectbox("Selectează", df_w["ticker"].tolist(), key="wl_sel", label_visibility="collapsed")
            with wac2:
                if st.button("🗑 Remove"):
                    remove_from_watchlist(sel_w); st.success(f"{sel_w} șters."); st.cache_data.clear(); st.rerun()
            with wac3:
                if st.button("🔄 Reload"):
                    st.cache_data.clear(); st.rerun()
            with wac4:
                rw   = df_w[df_w["ticker"]==sel_w].iloc[0]
                cw   = safe(rw, "Company","company_name")
                vw   = safe(rw, "Vol Ratio")
                rolw = safe(rw, "Role","top_insider_role")
                st.markdown(f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:.72rem;'
                            f'color:{MUTED};padding-top:8px">{sel_w} · <span style="color:{MUTED2}">'
                            f'{cw[:35]}</span> · score <b style="color:{TEXT2}">{rw["score"]}</b>'
                            f' · {vw} · {rolw}</div>', unsafe_allow_html=True)

            st.markdown("---")
            render_detail(sel_w)
