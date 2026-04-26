"""
Streamlit UI v4 — Smart Money Screener
- Tab Bullish Setups:  acumulare instituțională (call sweep + vol spike + sideways)
- Tab Bearish Setups:  distribuție / short oportunități (put sweep + short building)
- Tab Sector Heatmap:  rotație capital pe sectoare
- Tab Whale Persistence: footprint instituțional 21 zile
- Tab Watchlist:       monitorizare manuală
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
import streamlit as st
from app.db import (
    get_enriched, get_watchlist_enriched, remove_from_watchlist,
    add_to_watchlist, get_sector_stats, get_persistence_stats,
)

st.set_page_config(page_title="Smart Money Screener", layout="wide", page_icon="📡")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');
html, body, [class*="st-"] { font-family: 'IBM Plex Mono', monospace; font-size: 13px; }
.ai-box { background:#0d1117; border:1px solid #30363d; border-radius:8px;
    padding:14px 18px; margin-top:8px; line-height:1.7; }
.bull { color: #3fb950; font-weight: 600; }
.bear { color: #f85149; font-weight: 600; }
.dist { color: #d29922; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("📡 Smart Money Screener")

# ── Helpers ───────────────────────────────────────────────────────────────────

BULL_COLS = [
    "ticker", "company_name_display", "sector", "price", "vol_ratio",
    "options_signal", "pc_ratio", "squeeze_setup",
    "persistence_days", "score", "thesis",
]

BEAR_COLS = [
    "ticker", "company_name_display", "sector", "price", "vol_ratio",
    "options_signal", "pc_ratio", "short_signal", "short_float_pct",
    "net_insider_signal", "score", "thesis",
]


def _safe_df(data: list[dict], cols: list[str]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    present = [c for c in cols if c in df.columns]
    return df[present]


def _confluence(row) -> str:
    score   = float(row.get("score") or 0)
    persist = int(row.get("persistence_days") or 0)
    vol     = float(row.get("vol_ratio") or 0)
    if score >= 50 and persist >= 3 and vol >= 3:
        return "🔥 CONFLUENȚĂ"
    if score >= 50:
        return "⭐ HIGH SCORE"
    return ""


def _dir_icon(direction: str) -> str:
    return {"BULLISH": "🟢", "BEARISH": "🔴", "DISTRIBUTION": "🟠", "NEUTRAL": "⚪"}.get(direction, "⚪")


def _render_ai_panel(row: dict, key_suffix: str):
    ai_text = (row.get("ai_thesis_ro") or "").strip()
    if ai_text:
        st.success("🤖 Analiză AI disponibilă")
        st.markdown(f'<div class="ai-box">{ai_text}</div>', unsafe_allow_html=True)
    else:
        if st.button("🤖 Generează Analiză AI", key=f"ai_{key_suffix}"):
            with st.spinner("Claude Haiku analizează..."):
                try:
                    from collectors.enricher import get_ai_thesis
                    result = get_ai_thesis(row)
                except Exception as e:
                    result = f"Eroare: {e}"
            if result:
                st.markdown(f'<div class="ai-box">{result}</div>', unsafe_allow_html=True)
            else:
                st.warning("Setează ANTHROPIC_API_KEY și asigură-te că score ≥ 55.")


def _render_detail_row(row: dict, key_suffix: str):
    """Expander complet pentru un ticker — date options + short + insider + AI."""
    ticker    = row.get("ticker", "")
    company   = row.get("company_name_display") or row.get("company_name") or ""
    score     = row.get("score", 0)
    direction = row.get("direction", "NEUTRAL")
    icon      = _dir_icon(direction)
    conf      = _confluence(row)

    label = f"{icon} {ticker}  |  {company}  |  Score: {score}  |  {conf}"
    with st.expander(label, expanded=False):

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Score",       score)
        m2.metric("Vol Ratio",   f"{row.get('vol_ratio',0):.1f}x")
        m3.metric("P/C Ratio",   f"{row.get('pc_ratio','N/A')}")
        m4.metric("Persistență", f"{row.get('persistence_days',0)}d/21d")
        m5.metric("Short Ratio", f"{row.get('short_sale_ratio') or row.get('short_float_pct') or 'N/A'}")
        m6.metric("Inst. Own",   f"{row.get('inst_own_pct') or 'N/A'}")

        st.markdown(f"**Thesis:** {row.get('thesis','')}")
        st.markdown(
            f"**Options:** {row.get('options_signal','')} | "
            f"Calls neobișnuite: {row.get('unusual_call_strikes',0)} strike-uri | "
            f"Puts neobișnuite: {row.get('unusual_put_strikes',0)} strike-uri"
        )

        ins_buy  = row.get("insider_buys_90d", 0)
        ins_sell = row.get("insider_sells_90d", 0)
        if ins_buy or ins_sell:
            buy_val  = row.get("insider_buy_value") or 0
            sell_val = row.get("insider_sell_value") or 0
            role     = row.get("top_insider_role", "")
            plan_note = " [10b5-1 plan]" if row.get("is_10b5_plan") else ""
            st.markdown(
                f"**Insider (context):** {ins_buy}× buy ${buy_val:,.0f} / "
                f"{ins_sell}× sell ${sell_val:,.0f}{plan_note} — *{role}*"
            )

        _render_ai_panel(row, key_suffix=key_suffix)


# ── Tabs ──────────────────────────────────────────────────────────────────────

tabs = st.tabs([
    "🟢 Bullish Setups",
    "🔴 Bearish / Distribution",
    "🌡️ Sector Heatmap",
    "🐳 Whale Persistence",
    "⭐ Watchlist",
])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Bullish Setups
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("🟢 Bullish Setups — Acumulare Instituțională")
    st.caption(
        "Call sweep + vol spike + sideways pattern = instituție care acumulează discret. "
        "Short squeeze setup = balenele știu că shorterii vor capitula."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        days_back  = st.selectbox("Perioadă", [1, 3, 7], index=0, key="bull_days")
    with col2:
        min_score  = st.slider("Scor minim", 0, 100, 20, step=10, key="bull_score")
    with col3:
        only_conf  = st.checkbox("Doar CONFLUENȚĂ", key="bull_conf")
    with col4:
        show_neut  = st.checkbox("Include NEUTRAL", value=True, key="bull_neut")

    all_data = get_enriched(days_back=days_back, min_score=min_score)

    bull_data = [
        r for r in all_data
        if r.get("direction") in (["BULLISH"] + (["NEUTRAL"] if show_neut else []))
    ]

    for r in bull_data:
        r["confluenta"] = _confluence(r)

    if only_conf:
        bull_data = [r for r in bull_data if "CONFLUENȚĂ" in r.get("confluenta", "")]

    if not bull_data:
        st.info("Niciun setup bullish găsit. Rulează `python collectors/run.py --phase enrich`")
    else:
        df_bull = _safe_df(bull_data, BULL_COLS + ["confluenta", "direction"])
        st.dataframe(df_bull.reset_index(drop=True), use_container_width=True, height=380)

        n_bull = sum(1 for r in bull_data if r.get("direction") == "BULLISH")
        n_sq   = sum(1 for r in bull_data if r.get("squeeze_setup"))
        n_call = sum(1 for r in bull_data if "CALL" in (r.get("options_signal") or ""))
        n_ai   = sum(1 for r in bull_data if r.get("ai_thesis_ro"))
        st.caption(
            f"Total: {len(bull_data)} | 🟢 BULLISH: {n_bull} | "
            f"🔥 Squeeze setups: {n_sq} | 📞 Call sweep: {n_call} | 🤖 AI: {n_ai}"
        )

        st.divider()
        st.subheader("Analiză Detaliată")
        priority = [r for r in bull_data if r.get("direction") == "BULLISH"] or bull_data
        for row in priority[:20]:
            _render_detail_row(row, key_suffix=f"bull_{row['ticker']}")

    st.divider()
    ticker_add = st.text_input("Adaugă în Watchlist:", placeholder="NVDA").upper()
    if st.button("➕ Add to Watchlist", key="bull_add") and ticker_add:
        add_to_watchlist(ticker_add)
        st.success(f"{ticker_add} adăugat!")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Bearish / Distribution
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("🔴 Bearish Setups — Distribuție / Short Oportunități")
    st.caption(
        "Put sweep = instituție se hedgează sau pariază la scădere. "
        "Distribuție = volum spike la prețuri mari + insider selling + put dominant."
    )

    col1, col2 = st.columns(2)
    with col1:
        bear_days  = st.selectbox("Perioadă", [1, 3, 7], index=0, key="bear_days")
    with col2:
        bear_score = st.slider("Scor minim", 0, 100, 15, step=5, key="bear_score")

    all_bear = get_enriched(days_back=bear_days, min_score=bear_score)
    bear_data = [
        r for r in all_bear
        if r.get("direction") in ("BEARISH", "DISTRIBUTION")
    ]

    if not bear_data:
        st.info("Niciun setup bearish detectat în perioada selectată.")
        st.markdown(
            "**Ce cauți manual:** tickers cu `options_signal = UNUSUAL_PUT_BUYING` "
            "sau `direction = DISTRIBUTION` + `net_insider_signal = DISTRIBUTION`"
        )
    else:
        df_bear = _safe_df(bear_data, BEAR_COLS + ["direction"])
        st.dataframe(
            df_bear.reset_index(drop=True),
            use_container_width=True,
            height=350,
        )

        n_dist = sum(1 for r in bear_data if r.get("direction") == "DISTRIBUTION")
        n_put  = sum(1 for r in bear_data if "PUT" in (r.get("options_signal") or ""))
        st.caption(
            f"Total: {len(bear_data)} | 🟠 DISTRIBUȚIE: {n_dist} | 🔴 BEARISH: {len(bear_data)-n_dist} | "
            f"Put sweep: {n_put}"
        )

        st.divider()
        st.subheader("Analiză Detaliată")
        for row in bear_data[:15]:
            _render_detail_row(row, key_suffix=f"bear_{row['ticker']}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: Sector Heatmap
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("🌡️ Sector Heatmap — Rotație Capital")
    st.caption("5+ tickers activi în același sector = Smart Money rotează acolo")

    sector_data = get_sector_stats(days_back=1)

    if not sector_data:
        st.info("Date sector indisponibile. Rulează scan + enrich mai întâi.")
    else:
        df_sec = pd.DataFrame(sector_data)

        in_play = df_sec[df_sec["in_play"] == True]
        if not in_play.empty:
            st.markdown("### 🔴 Sectoare IN PLAY")
            cols = st.columns(min(len(in_play), 4))
            for i, (_, row) in enumerate(in_play.iterrows()):
                with cols[i % 4]:
                    st.metric(
                        label=row["sector"],
                        value=f"{row['count']} tickers",
                        delta=f"avg vol {row['avg_vol']}x",
                    )
        st.divider()
        st.dataframe(
            df_sec.style.highlight_max(subset=["count", "avg_score", "avg_vol"], color="#0f5132"),
            use_container_width=True,
        )
        st.bar_chart(df_sec.set_index("sector")["count"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: Whale Persistence
# ─────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("🐳 Whale Footprint — Persistență 21 Zile")
    st.caption("Apariții repetate în scan = acumulare instituțională continuă, nu zgomot")

    persist_data = get_persistence_stats(days_back=21)

    if not persist_data:
        st.info("Insuficiente date istorice. Necesari minim 2 zile de scan.")
    else:
        df_p = pd.DataFrame(persist_data)

        whales = df_p[df_p["appearance_days"] >= 5]
        if not whales.empty:
            st.markdown(f"### 🐳 Whale Suspects ({len(whales)} tickers, 5+ zile)")
            st.dataframe(whales, use_container_width=True, height=200)
            st.divider()

        st.markdown("### Toate apariții (2+ zile)")
        st.dataframe(df_p, use_container_width=True, height=320)
        st.bar_chart(df_p.head(15).set_index("ticker")["appearance_days"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5: Watchlist
# ─────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("⭐ Watchlist")

    wl = get_watchlist_enriched()
    if not wl:
        st.info("Watchlist gol. Adaugă tickers din tab Bullish sau Bearish.")
    else:
        for r in wl:
            r["confluenta"] = _confluence(r)
            r["dir_icon"]   = _dir_icon(r.get("direction", "NEUTRAL"))

        wl_cols = ["ticker", "company_name_display", "sector", "price", "direction",
                   "vol_ratio", "options_signal", "score", "thesis"]
        st.dataframe(_safe_df(wl, wl_cols + ["confluenta"]), use_container_width=True, height=320)

        st.divider()
        st.subheader("Analiză Detaliată Watchlist")
        for row in wl:
            _render_detail_row(row, key_suffix=f"wl_{row['ticker']}")

        st.divider()
        ticker_rm = st.text_input("Șterge ticker:", placeholder="AAPL").upper()
        if st.button("🗑️ Remove") and ticker_rm:
            remove_from_watchlist(ticker_rm)
            st.success(f"{ticker_rm} șters!")
            st.rerun()
