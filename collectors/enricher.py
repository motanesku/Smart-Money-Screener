"""
Enricher v3 — îmbunătățiri față de v2:

FIX 1: score_insider calculat pe net_signal (buy vs sell real, nu orice Form 4)
FIX 2: penalty pentru insider SELLING aplicat în score total
FIX 3: short interest integrat real din FINRA (nu mai e placeholder 0)

NOU: score_short_squeeze — combină FINRA short ratio + vol spike + insider buys
NOU: sideways_score — detectează acumulare discretă (preț stabil + vol spikes)
NOU: ai_thesis_ro — analiză Haiku în română (rulează doar dacă score >= 60)
"""

import os
import sys
from datetime import date

import yfinance as yf

from app.db import get_client


# ── Profil companie ────────────────────────────────────────────────────────────

def get_profile(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        return {
            "name":       info.get("longName") or info.get("shortName") or "",
            "sector":     info.get("sector") or "",
            "industry":   info.get("industry") or "",
            "market_cap": int(info.get("marketCap") or 0),
            "pe_ratio":   info.get("trailingPE"),
            "beta":       info.get("beta"),
        }
    except Exception as e:
        print(f"  [yfinance] {ticker} profil eroare: {e}")
        return {}


# ── Persistence count ──────────────────────────────────────────────────────────

def get_persistence_count(ticker: str) -> int:
    try:
        from datetime import timedelta
        since = (date.today() - timedelta(days=21)).isoformat()
        res = (
            get_client()
            .table("scan_results")
            .select("scan_date")
            .eq("ticker", ticker.upper())
            .gte("scan_date", since)
            .execute()
        )
        return len({row["scan_date"] for row in (res.data or [])})
    except Exception as e:
        print(f"  [persistence] {ticker} eroare: {e}")
        return 0


# ── Sideways detector (acumulare discretă) ────────────────────────────────────

def get_sideways_score(ticker: str, scan_data: dict | None = None) -> tuple[int, str]:
    """
    Detectează pattern de acumulare: preț sideways (range < 8%) + vol spikes multiple.
    Balenele intră treptat pe 2-3 săptămâni fără să miște prețul.

    Returns: (scor 0-15, descriere)
    """
    try:
        hist = yf.Ticker(ticker).history(period="21d", interval="1d", auto_adjust=True)
        if len(hist) < 10:
            return 0, "INSUFFICIENT_DATA"

        closes = hist["Close"].dropna()
        volumes = hist["Volume"].dropna()

        price_range_pct = (closes.max() - closes.min()) / closes.mean()
        avg_vol = volumes.mean()
        vol_spikes = int((volumes > avg_vol * 2).sum())

        # Pattern ideal: preț strâns (< 8%) + minim 3 zile cu vol spike
        if price_range_pct < 0.05 and vol_spikes >= 4:
            return 15, "STRONG_ACCUMULATION_PATTERN"
        if price_range_pct < 0.08 and vol_spikes >= 3:
            return 10, "ACCUMULATION_PATTERN"
        if price_range_pct < 0.10 and vol_spikes >= 2:
            return 5, "WEAK_ACCUMULATION"
        return 0, "NO_PATTERN"

    except Exception as e:
        print(f"  [sideways] {ticker} eroare: {e}")
        return 0, "ERROR"


# ── Score helpers ──────────────────────────────────────────────────────────────

def _score_volume(vol_ratio: float) -> tuple[int, str]:
    """Scor volum 0-40."""
    if vol_ratio >= 5:
        return 40, "EXTREME_SPIKE"
    if vol_ratio >= 3:
        return 30, "HIGH_SPIKE"
    if vol_ratio >= 2:
        return 20, "SPIKE"
    return 10, "ELEVATED"


def _score_insider(insider: dict) -> tuple[int, str]:
    """
    Scor insider 0-30 bazat pe net_signal REAL (buy vs sell).
    FIX față de v2: nu mai numărăm orice Form 4 ca buy.
    """
    net_signal  = insider.get("net_signal", "NEUTRAL")
    buys        = insider.get("buys", 0)
    role_score  = insider.get("role_score", 3)

    if net_signal == "ACCUMULATION":
        if buys >= 5 or role_score >= 9:   # CEO/CFO buying agresiv
            return 30, "HEAVY_INSIDER_BUYING"
        if buys >= 3 or role_score >= 7:
            return 20, "INSIDER_BUYING"
        if buys >= 1:
            return 10, "LIGHT_INSIDER_BUYING"
    elif net_signal == "MIXED":
        # Buying și selling simultan = semnal amestecat, scor redus
        return 5, "MIXED_INSIDER"
    elif net_signal == "DISTRIBUTION":
        # Selling → scorul vine din penalty, nu bonus
        return 0, "INSIDER_SELLING"

    return 0, "NO_INSIDER_ACTIVITY"


def _score_persistence(count: int) -> int:
    """Bonus 0-20 pentru persistență whale."""
    return min(count * 4, 20)


# ── Haiku AI Analysis ─────────────────────────────────────────────────────────

def get_ai_thesis(enriched_data: dict) -> str:
    """
    Apelează Claude Haiku pentru o analiză în română din perspectiva unui
    analist senior Smart Money. Rulează doar dacă score >= 60.

    Integrare: apelăm Anthropic API direct (fără SDK — nu adăugăm dependențe noi).
    Necesită variabila de mediu ANTHROPIC_API_KEY.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    score = int(enriched_data.get("score") or 0)
    if score < 60:
        return ""  # Nu consumăm tokens pentru semnale slabe

    try:
        import requests as req

        ticker         = enriched_data.get("ticker", "N/A")
        sector         = enriched_data.get("sector", "N/A")
        vol_ratio      = enriched_data.get("vol_ratio", 0)
        persist        = enriched_data.get("score_insider_quality", 0) // 4  # reconvertim
        insider_buys   = enriched_data.get("insider_buys_90d", 0)
        insider_sells  = enriched_data.get("insider_sells_90d", 0)
        insider_signal = enriched_data.get("insider_signal", "N/A")
        top_role       = enriched_data.get("top_insider_role", "N/A")
        short_signal   = enriched_data.get("short_signal", "N/A")
        short_ratio    = enriched_data.get("short_sale_ratio")
        rs_sector      = enriched_data.get("rs_vs_sector")
        heat_score     = enriched_data.get("sector_heat_score", 0)
        thesis_raw     = enriched_data.get("thesis", "N/A")
        squeeze        = enriched_data.get("squeeze_setup", False)
        is_10b5        = enriched_data.get("is_10b5_plan", False)
        net_signal     = enriched_data.get("net_insider_signal", "N/A")
        penalty        = enriched_data.get("score_penalty", 0)

        short_str = f"{short_ratio:.1%}" if short_ratio else "N/A"
        rs_str    = f"{rs_sector:+.2%}" if rs_sector else "N/A"

        prompt = f"""Ești un analist senior cu 20 de ani experiență în urmărirea fluxurilor Smart Money (balene, instituții, insideri).
Analizează datele de mai jos și oferă o opinie CONCISĂ în română, maxim 120 de cuvinte.

=== DATE TICKER: {ticker} ===
Sector: {sector} | Heat Score sector: {heat_score} companii active
Score total: {score}/100 | Relative Strength vs ETF sector: {rs_str}
Volume Ratio: {vol_ratio}x față de medie 20 zile
Persistență: {persist} zile din ultimele 21

INSIDER DATA (90 zile):
  Cumpărări: {insider_buys} tranzacții | Vânzări: {insider_sells} tranzacții
  Net Signal: {net_signal} | Rol: {top_role}
  Este plan 10b5-1 (vânzare programată): {is_10b5}
  Penalizare aplicată: {penalty} puncte

SHORT DATA:
  Short Ratio: {short_str} | Semnal: {short_signal}
  Setup Short Squeeze: {squeeze}

Thesis curentă sistem: {thesis_raw}

Răspunde STRICT în formatul:
VERDICT: [ACUMULARE / DISTRIBUȚIE / FALS SEMNAL / INCERT]
RAȚIONAMENT: [2-3 propoziții cu cel mai important argument]
INVALIDARE: [ce ar anula acest semnal]
ÎNCREDERE: [RIDICATĂ / MEDIE / SCĂZUTĂ]"""

        response = req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 350,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("content", [{}])[0].get("text", "").strip()
        print(f"  [Haiku] {ticker} analiză generată ({len(text)} chars)")
        return text

    except Exception as e:
        print(f"  [Haiku] {ticker} eroare: {e}")
        return ""


# ── Core enrich ────────────────────────────────────────────────────────────────

def enrich_single(ticker: str, scan_data: dict | None = None) -> dict:
    ticker = ticker.upper()
    print(f"  Enriching {ticker}...")

    profile   = get_profile(ticker)

    from collectors.edgar import get_insider_data_edgar
    insider   = get_insider_data_edgar(ticker, days_back=90)

    from collectors.finra import get_short_data, score_short
    short     = get_short_data(ticker, days_back=5)

    p_count   = get_persistence_count(ticker)

    vol_ratio    = float((scan_data or {}).get("vol_ratio", 0))
    price        = (scan_data or {}).get("price")
    volume       = int((scan_data or {}).get("volume", 0))
    avg_vol_20d  = int((scan_data or {}).get("avg_volume_20d", 0))
    rs_vs_sector = (scan_data or {}).get("rs_vs_sector")
    sector_heat  = int((scan_data or {}).get("sector_heat_score", 0))

    # Scoruri componente
    s_vol,     sig_vol     = _score_volume(vol_ratio)
    s_insider, sig_insider = _score_insider(insider)
    s_persist              = _score_persistence(p_count)
    s_short, sig_short     = score_short(short, vol_ratio=vol_ratio, insider_buys=insider.get("buys", 0))
    s_sideways, sig_side   = get_sideways_score(ticker, scan_data)

    # Penalizare insider selling (FIX v3 — în v2 nu exista)
    penalty = insider.get("penalty", 0)

    # Score total cu penalty
    raw_score   = s_vol + s_insider + s_persist + s_short + s_sideways
    total_score = max(0, min(raw_score + penalty, 100))

    # Thesis text
    thesis_parts = []
    if sig_vol in ("EXTREME_SPIKE", "HIGH_SPIKE"):
        thesis_parts.append(f"Vol {vol_ratio:.1f}x")
    if p_count >= 3:
        thesis_parts.append(f"Persistent {p_count}d/21d")
    if insider.get("buys", 0) >= 1 and insider.get("net_signal") == "ACCUMULATION":
        thesis_parts.append(f"Insider buy ${insider.get('buy_value', 0):,.0f} ({insider.get('top_role', '')})")
    if insider.get("net_signal") == "DISTRIBUTION":
        plan_note = " [10b5 plan]" if insider.get("is_10b5_plan") else " ⚠️"
        thesis_parts.append(f"Insider SELL ${insider.get('sell_value', 0):,.0f}{plan_note}")
    if short.get("squeeze_setup"):
        thesis_parts.append("SHORT SQUEEZE SETUP")
    elif sig_short == "SHORT_COVERING":
        thesis_parts.append("Short covering")
    if sig_side in ("STRONG_ACCUMULATION_PATTERN", "ACCUMULATION_PATTERN"):
        thesis_parts.append("Sideways accumulation")
    thesis = " | ".join(thesis_parts) if thesis_parts else "Volume alert"

    enriched = {
        "ticker":               ticker,
        "enrich_date":          date.today().isoformat(),
        "company_name":         profile.get("name", ""),
        "sector":               profile.get("sector", ""),
        "industry":             profile.get("industry", ""),
        "market_cap":           profile.get("market_cap", 0),
        "price":                price,
        "volume":               volume,
        "avg_volume_20d":       avg_vol_20d,
        "vol_ratio":            round(vol_ratio, 4),
        "rs_vs_sector":         rs_vs_sector,
        "sector_heat_score":    sector_heat,

        # Insider — date reale (FIX v3)
        "insider_buys_90d":     insider.get("buys", 0),
        "insider_buy_value":    insider.get("buy_value", 0.0),
        "insider_sells_90d":    insider.get("sells", 0),
        "insider_sell_value":   insider.get("sell_value", 0.0),
        "top_insider_role":     insider.get("top_role", "N/A"),
        "net_insider_signal":   insider.get("net_signal", "NEUTRAL"),
        "is_10b5_plan":         insider.get("is_10b5_plan", False),

        # Short — date reale FINRA (NOU v3)
        "short_interest_pct":    short.get("short_sale_ratio"),
        "short_sale_volume":     short.get("short_sale_volume", 0),
        "total_volume_reported": short.get("total_volume_reported", volume),
        "short_sale_ratio":      short.get("short_sale_ratio"),
        "short_flow_signal":     short.get("short_flow_signal", ""),
        "short_signal":          short.get("short_signal", ""),
        "avg_short_ratio_5d":    short.get("avg_short_ratio_5d"),
        "squeeze_setup":         short.get("squeeze_setup", False),

        # Ownership placeholder (13F — implementare viitoare)
        "ownership_form":        "",
        "ownership_holder":      "",
        "ownership_pct":         None,
        "ownership_signal":      "",
        "ownership_signal_text": "",

        # Fundamentale
        "pe_ratio":              profile.get("pe_ratio"),
        "beta":                  profile.get("beta"),
        "inst_ownership_pct":    None,

        # Scoruri
        "score":                 total_score,
        "score_volume":          s_vol,
        "score_insider":         s_insider,
        "score_insider_quality": s_persist,
        "score_ownership":       0,
        "score_short_interest":  s_short,
        "score_short_flow":      s_sideways,
        "score_fundamental":     0,
        "score_penalty":         penalty,

        # Semnale
        "volume_signal":         sig_vol,
        "insider_signal":        sig_insider,
        "short_squeeze_signal":  sig_short,
        "sideways_signal":       sig_side,
        "thesis":                thesis,
    }

    # Haiku AI thesis (rulează doar dacă score >= 60 și ANTHROPIC_API_KEY setat)
    ai_thesis = get_ai_thesis(enriched)
    if ai_thesis:
        enriched["ai_thesis_ro"] = ai_thesis

    return enriched


# ── Public API ─────────────────────────────────────────────────────────────────

def enrich_candidates(candidates: list[dict]) -> list[dict]:
    return [enrich_single(c["ticker"], scan_data=c) for c in candidates if c.get("ticker")]


def enrich_watchlist(tickers: list[str], scan_results: list[dict]) -> list[dict]:
    scan_map = {r["ticker"].upper(): r for r in scan_results if "ticker" in r}
    return [enrich_single(t, scan_data=scan_map.get(t.upper())) for t in tickers]


# ── CLI test ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if candidates:
        res = enrich_candidates(candidates)
        save_enriched(res)
        print(f"Salvat {len(res)} tickers enriched")
    else:
        print("Niciun candidat de enriched")
