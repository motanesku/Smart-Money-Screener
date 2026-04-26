"""
Streamlit UI v2 — implementează arhitectura v2:
- Tab Candidates: tabel cu score + badge CONFLUENȚĂ + filtru
- Tab Sector Heatmap: sectoare In Play (>= 5 tickers)
- Tab Whale Persistence: tickers cu apariții multiple în 21 zile
- Tab Watchlist: watchlist cu enrich live
"""
import sys, os
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
html, body, [class*="st-"] { font-family: 'IBM Plex Mono', monospace; }
.badge-confluence { background:#0969da; color:white; padding:2px 8px;
    border-radius:4px; font-size:11px; font-weight:600; }
.badge-inplay { background:#d93025; color:white; padding:2px 8px;
    border-radius:4px; font-size:11px; font-weight:600; }
.badge-persistent { background:#6f42c1; color:white; padding:2px 8px;
    border-radius:4px; font-size:11px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

st.title("📡 Smart Money Screener")

# ── Helpers ────────────────────────────────────────────────────────────────────

SCORE_COLS = ["score", "score_volume", "score_insider", "score_insider_quality",
              "score_ownership", "score_short_interest"]

DISPLAY_COLS = [
    "ticker", "company_name_display", "sector", "price", "vol_ratio",
    "insider_buys_90d", "persistence_days", "score",
    "volume_signal", "insider_signal", "thesis",
]

def _safe_df(data: list[dict], cols: list[str] | None = None) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if cols:
        present = [c for c in cols if c in df.columns]
        df = df[present]
    return df


def _score_color(val):
    if val >= 70: return "background-color:#0f5132; color:white"
    if val >= 50: return "background-color:#0969da; color:white"
    if val >= 30: return "background-color:#664d03; color:white"
    return ""


def _confluence_badge(row) -> str:
    """Badge dacă score >= 50 AND persistence >= 3 AND vol_ratio >= 3."""
    score    = float(row.get("score") or 0)
    persist  = int(row.get("persistence_days") or 0)
    vol      = float(row.get("vol_ratio") or 0)
    if score >= 50 and persist >= 3 and vol >= 3:
        return "🔥 CONFLUENȚĂ"
    if score >= 50:
        return "⭐ HIGH SCORE"
    return ""


# ── Tabs ───────────────────────────────────────────────────────────────────────

tabs = st.tabs(["🚀 Candidates", "🌡️ Sector Heatmap", "🐳 Whale Persistence", "⭐ Watchlist"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Candidates
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Candidați Smart Money")

    col1, col2, col3 = st.columns(3)
    with col1:
        days_back = st.selectbox("Perioada", [1, 3, 7], index=0)
    with col2:
        min_score = st.slider("Scor minim", 0, 100, 30, step=10)
    with col3:
        only_confluence = st.checkbox("Doar CONFLUENȚĂ", value=False)

    data = get_enriched(days_back=days_back, min_score=min_score)

    if not data:
        st.info("Niciun candidat găsit. Rulează `python collectors/run.py --phase enrich`")
    else:
        for row in data:
            row["confluenta"] = _confluence_badge(row)

        if only_confluence:
            data = [r for r in data if "CONFLUENȚĂ" in r.get("confluenta", "")]

        df = _safe_df(data, DISPLAY_COLS + ["confluenta", "sector_in_play", "rs_vs_sector"])
        st.dataframe(
            df.reset_index(drop=True),
            width="stretch",
            height=450,
        )

        st.caption(f"Total: {len(df)} tickers | 🔥 Confluență: {sum(1 for r in data if 'CONFLUENȚĂ' in r.get('confluenta',''))}")

        # Buton add to watchlist
        st.divider()
        ticker_add = st.text_input("Adaugă ticker în Watchlist:", placeholder="AAPL").upper()
        if st.button("➕ Add to Watchlist") and ticker_add:
            add_to_watchlist(ticker_add)
            st.success(f"{ticker_add} adăugat!")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Sector Heatmap
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("🌡️ Sector Heatmap — Rotație Capital")
    st.caption("Sectoarele cu 5+ tickers active sunt marcate **IN PLAY** (Smart Money rotates here)")

    sector_data = get_sector_stats(days_back=1)

    if not sector_data:
        st.info("Date sector indisponibile. Rulează scan + enrich mai întâi.")
    else:
        df_sec = pd.DataFrame(sector_data)

        # Vizual: In Play badges
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

        # Tabel complet
        st.dataframe(
            df_sec.style.highlight_max(subset=["count", "avg_score", "avg_vol"],
                                        color="#0f5132"),
            width="stretch",
        )

        # Bar chart
        st.bar_chart(df_sec.set_index("sector")["count"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: Whale Persistence
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("🐳 Whale Footprint — Persistență 21 Zile")
    st.caption("Tickers care au apărut repetat în scan = acumulare instituțională")

    persist_data = get_persistence_stats(days_back=21)

    if not persist_data:
        st.info("Insuficiente date istorice. Necesari minim 2 zile de scan.")
    else:
        df_p = pd.DataFrame(persist_data)

        # Highlight tickeri cu 5+ apariții
        whales = df_p[df_p["appearance_days"] >= 5]
        if not whales.empty:
            st.markdown(f"### 🐳 Whale Suspects ({len(whales)} tickers, 5+ zile)")
            st.dataframe(whales, width="stretch", height=200)
            st.divider()

        st.markdown("### Toate apariții (2+ zile)")
        st.dataframe(df_p, width="stretch", height=350)

        # Bar chart top 15
        top15 = df_p.head(15)
        st.bar_chart(top15.set_index("ticker")["appearance_days"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: Watchlist
# ─────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("⭐ Watchlist")

    wl = get_watchlist_enriched()
    if not wl:
        st.info("Watchlist gol. Adaugă tickers din tab Candidates.")
    else:
        for row in wl:
            row["confluenta"] = _confluence_badge(row)

        df_wl = _safe_df(wl, DISPLAY_COLS + ["confluenta"])
        st.dataframe(df_wl, width="stretch", height=400)

        st.divider()
        ticker_rm = st.text_input("Șterge ticker:", placeholder="AAPL").upper()
        if st.button("🗑️ Remove") and ticker_rm:
            remove_from_watchlist(ticker_rm)
            st.success(f"{ticker_rm} șters!")
            st.rerun()
