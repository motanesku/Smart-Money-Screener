"""
Streamlit UI v3 — Smart Money Screener
- Tab Candidates: tabel + badge CONFLUENȚĂ + Analiză AI per ticker
- Tab Sector Heatmap: sectoare In Play (>= 5 tickers activi)
- Tab Whale Persistence: footprint instituțional 21 zile
- Tab Watchlist: monitorizare manuală cu enrich live
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
html, body, [class*="st-"] { font-family: 'IBM Plex Mono', monospace; }
.badge-confluence { background:#0969da; color:white; padding:2px 8px;
    border-radius:4px; font-size:11px; font-weight:600; }
.badge-inplay { background:#d93025; color:white; padding:2px 8px;
    border-radius:4px; font-size:11px; font-weight:600; }
.badge-persistent { background:#6f42c1; color:white; padding:2px 8px;
    border-radius:4px; font-size:11px; font-weight:600; }
.ai-box { background:#0d1117; border:1px solid #30363d; border-radius:8px;
    padding:14px 18px; margin-top:8px; font-size:13px; line-height:1.6; }
</style>
""", unsafe_allow_html=True)

st.title("📡 Smart Money Screener")

# ── Helpers ─────────────────────────────────────────────────────────────────────

DISPLAY_COLS = [
    "ticker", "company_name_display", "sector", "price", "vol_ratio",
    "insider_buys_90d", "insider_sells_90d", "net_insider_signal",
    "squeeze_setup", "persistence_days", "score", "thesis",
]


def _safe_df(data: list[dict], cols: list[str] | None = None) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if cols:
        present = [c for c in cols if c in df.columns]
        df = df[present]
    return df


def _confluence_badge(row) -> str:
    score   = float(row.get("score") or 0)
    persist = int(row.get("persistence_days") or 0)
    vol     = float(row.get("vol_ratio") or 0)
    if score >= 50 and persist >= 3 and vol >= 3:
        return "🔥 CONFLUENȚĂ"
    if score >= 50:
        return "⭐ HIGH SCORE"
    return ""


def _generate_ai(row: dict) -> str:
    """Apelează Haiku live pentru un ticker — folosit din butonul manual."""
    try:
        from collectors.enricher import get_ai_thesis
        return get_ai_thesis(row)
    except Exception as e:
        return f"Eroare: {e}"


def _render_ai_panel(row: dict, key_suffix: str):
    """Afișează AI thesis dacă există sau buton de generare dacă nu există."""
    ai_text = (row.get("ai_thesis_ro") or "").strip()
    if ai_text:
        st.success("🤖 Analiză AI disponibilă (generată la enrich)")
        st.markdown(f'<div class="ai-box">{ai_text}</div>', unsafe_allow_html=True)
    else:
        if st.button(f"🤖 Generează Analiză AI", key=f"ai_btn_{key_suffix}"):
            with st.spinner("Claude Haiku analizează..."):
                result = _generate_ai(row)
            if result:
                st.markdown(f'<div class="ai-box">{result}</div>', unsafe_allow_html=True)
            else:
                st.warning("Setează variabila de mediu ANTHROPIC_API_KEY și asigură-te că score >= 60.")


# ── Tabs ─────────────────────────────────────────────────────────────────────────

tabs = st.tabs(["🚀 Candidates", "🌡️ Sector Heatmap", "🐳 Whale Persistence", "⭐ Watchlist"])


# ─────────────────────────────────────────────────────────────────────────────────
# TAB 1: Candidates
# ─────────────────────────────────────────────────────────────────────────────────
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
        st.dataframe(df.reset_index(drop=True), use_container_width=True, height=400)

        confluence_rows = [r for r in data if "CONFLUENȚĂ" in r.get("confluenta", "")]
        n_confluence = len(confluence_rows)
        n_ai_ready   = sum(1 for r in confluence_rows if r.get("ai_thesis_ro"))
        st.caption(
            f"Total: {len(df)} tickers | "
            f"🔥 Confluență: {n_confluence} | "
            f"🤖 AI analizat: {n_ai_ready}/{n_confluence}"
        )

        # ── Secțiunea AI Analysis (doar pentru tickers cu CONFLUENȚĂ) ──────────
        if confluence_rows:
            st.divider()
            st.subheader(f"🔥 Analiză AI — {n_confluence} Confluențe Detectate")
            st.caption(
                "Analizele pre-generate sunt salvate în Supabase la faza `enrich` (score ≥ 60). "
                "Poți genera live oricând cu butonul de mai jos."
            )

            for row in confluence_rows:
                ticker   = row.get("ticker", "N/A")
                company  = row.get("company_name_display") or row.get("company_name") or ""
                score    = row.get("score", 0)
                vol      = row.get("vol_ratio", 0)
                persist  = row.get("persistence_days", 0)
                sector   = row.get("sector", "")
                squeeze  = "✅ SQUEEZE SETUP" if row.get("squeeze_setup") else ""
                net_sig  = row.get("net_insider_signal", "")

                label = f"🔥 {ticker}  |  {company}  |  Score: {score}  |  Vol: {vol:.1f}x  |  {sector}"
                with st.expander(label, expanded=False):
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Score", score)
                    m2.metric("Vol Ratio", f"{vol:.1f}x")
                    m3.metric("Persistență", f"{persist}d/21d")
                    m4.metric("Insider Net", net_sig or "N/A")
                    m5.metric("Short Squeeze", squeeze or "—")

                    st.markdown(f"**Thesis:** {row.get('thesis','')}")

                    if row.get("insider_buys_90d") or row.get("insider_sells_90d"):
                        ins_buy  = row.get("insider_buys_90d", 0)
                        ins_sell = row.get("insider_sells_90d", 0)
                        buy_val  = row.get("insider_buy_value") or 0
                        sell_val = row.get("insider_sell_value") or 0
                        role     = row.get("top_insider_role", "")
                        plan     = " [10b5-1]" if row.get("is_10b5_plan") else ""
                        st.markdown(
                            f"**Insider:** {ins_buy} buy (${buy_val:,.0f}) / "
                            f"{ins_sell} sell (${sell_val:,.0f}){plan} — *{role}*"
                        )

                    _render_ai_panel(row, key_suffix=ticker)

        # ── Add to Watchlist ──────────────────────────────────────────────────
        st.divider()
        ticker_add = st.text_input("Adaugă ticker în Watchlist:", placeholder="AAPL").upper()
        if st.button("➕ Add to Watchlist") and ticker_add:
            add_to_watchlist(ticker_add)
            st.success(f"{ticker_add} adăugat!")


# ─────────────────────────────────────────────────────────────────────────────────
# TAB 2: Sector Heatmap
# ─────────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("🌡️ Sector Heatmap — Rotație Capital")
    st.caption("Sectoarele cu 5+ tickers active sunt marcate **IN PLAY** — Smart Money rotates here")

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
            df_sec.style.highlight_max(
                subset=["count", "avg_score", "avg_vol"], color="#0f5132"
            ),
            use_container_width=True,
        )
        st.bar_chart(df_sec.set_index("sector")["count"])


# ─────────────────────────────────────────────────────────────────────────────────
# TAB 3: Whale Persistence
# ─────────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("🐳 Whale Footprint — Persistență 21 Zile")
    st.caption("Tickers care au apărut repetat în scan = acumulare instituțională continuă")

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
        st.dataframe(df_p, use_container_width=True, height=350)

        top15 = df_p.head(15)
        st.bar_chart(top15.set_index("ticker")["appearance_days"])


# ─────────────────────────────────────────────────────────────────────────────────
# TAB 4: Watchlist
# ─────────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("⭐ Watchlist")

    wl = get_watchlist_enriched()
    if not wl:
        st.info("Watchlist gol. Adaugă tickers din tab Candidates.")
    else:
        for row in wl:
            row["confluenta"] = _confluence_badge(row)

        df_wl = _safe_df(wl, DISPLAY_COLS + ["confluenta"])
        st.dataframe(df_wl, use_container_width=True, height=350)

        # AI panels pentru watchlist
        wl_confluence = [r for r in wl if "CONFLUENȚĂ" in r.get("confluenta", "")]
        if wl_confluence:
            st.divider()
            st.subheader("🔥 Confluențe în Watchlist")
            for row in wl_confluence:
                ticker = row.get("ticker", "N/A")
                score  = row.get("score", 0)
                with st.expander(f"🔥 {ticker} | Score: {score}", expanded=False):
                    st.markdown(f"**Thesis:** {row.get('thesis','')}")
                    _render_ai_panel(row, key_suffix=f"wl_{ticker}")

        st.divider()
        ticker_rm = st.text_input("Șterge ticker:", placeholder="AAPL").upper()
        if st.button("🗑️ Remove") and ticker_rm:
            remove_from_watchlist(ticker_rm)
            st.success(f"{ticker_rm} șters!")
            st.rerun()
