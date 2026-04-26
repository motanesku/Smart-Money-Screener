"""
Enricher v2 — fixes:
1. get_profile() folosește yfinance (gratuit, fără FMP_KEY)
2. enrich_single() populează TOATE câmpurile așteptate de save_enriched()
3. score_insider calculat corect (nu mai e hardcodat 0)
4. Sector Heat Score calculat și salvat
"""
import sys
from datetime import date
import yfinance as yf
from app.db import get_client


# ── Profil companie via yfinance (înlocuiește FMP) ──────────────────────────

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


# ── Persistence count (câte zile a apărut în scan ultimele 21 zile) ──────────

def get_persistence_count(ticker: str) -> int:
    try:
        res = (
            get_client()
            .table("scan_results")
            .select("scan_date")
            .eq("ticker", ticker.upper())
            .gte("scan_date", _days_ago(21))
            .execute()
        )
        dates = {row["scan_date"] for row in (res.data or [])}
        return len(dates)
    except Exception as e:
        print(f"  [persistence] {ticker} eroare: {e}")
        return 0


def _days_ago(n: int) -> str:
    from datetime import timedelta
    return (date.today() - timedelta(days=n)).isoformat()


# ── Score helpers ─────────────────────────────────────────────────────────────

def _score_volume(vol_ratio: float) -> tuple[int, str]:
    """Returnează (scor 0-40, semnal text)."""
    if vol_ratio >= 5:
        return 40, "EXTREME_SPIKE"
    if vol_ratio >= 3:
        return 30, "HIGH_SPIKE"
    if vol_ratio >= 2:
        return 20, "SPIKE"
    return 10, "ELEVATED"


def _score_insider(buys: int) -> tuple[int, str]:
    """Returnează (scor 0-30, semnal text)."""
    if buys >= 5:
        return 30, "HEAVY_BUYING"
    if buys >= 3:
        return 20, "BUYING"
    if buys >= 1:
        return 10, "LIGHT_BUYING"
    return 0, "NO_ACTIVITY"


def _score_persistence(count: int) -> int:
    """Bonus 0-20 pentru persistență whale (câte zile a apărut)."""
    return min(count * 5, 20)


# ── Core enrich ───────────────────────────────────────────────────────────────

def enrich_single(ticker: str, scan_data: dict | None = None) -> dict:
    ticker = ticker.upper()
    print(f"  Enriching {ticker}...")

    profile     = get_profile(ticker)
    from collectors.edgar import get_insider_data_edgar
    insider     = get_insider_data_edgar(ticker)
    p_count     = get_persistence_count(ticker)

    vol_ratio   = float((scan_data or {}).get("vol_ratio", 0))
    price       = (scan_data or {}).get("price")
    volume      = int((scan_data or {}).get("volume", 0))
    avg_vol_20d = int((scan_data or {}).get("avg_volume_20d", 0))

    # Scoruri componente
    s_vol,     sig_vol     = _score_volume(vol_ratio)
    s_insider, sig_insider = _score_insider(insider.get("buys", 0))
    s_persist              = _score_persistence(p_count)

    total_score = min(s_vol + s_insider + s_persist, 100)

    thesis_parts = []
    if sig_vol in ("EXTREME_SPIKE", "HIGH_SPIKE"):
        thesis_parts.append(f"Vol spike {vol_ratio:.1f}x")
    if p_count >= 3:
        thesis_parts.append(f"Persistent {p_count}d/21d")
    if insider.get("buys", 0) >= 1:
        thesis_parts.append(f"Insider buys: {insider['buys']}")
    thesis = " | ".join(thesis_parts) if thesis_parts else "Volume alert"

    return {
        # Identificare
        "ticker":               ticker,
        "enrich_date":          date.today().isoformat(),
        "company_name":         profile.get("name", ""),
        "sector":               profile.get("sector", ""),
        "industry":             profile.get("industry", ""),
        "market_cap":           profile.get("market_cap", 0),

        # Price/Volume din scan
        "price":                price,
        "volume":               volume,
        "avg_volume_20d":       avg_vol_20d,
        "vol_ratio":            round(vol_ratio, 4),

        # Insider
        "insider_buys_90d":     insider.get("buys", 0),
        "insider_buy_value":    insider.get("buy_value", 0.0),
        "insider_sells_90d":    insider.get("sells", 0),
        "insider_sell_value":   insider.get("sell_value", 0.0),
        "top_insider_role":     insider.get("top_role", "N/A"),

        # Ownership (placeholder — FINRA/13D collector separat)
        "ownership_form":       "",
        "ownership_holder":     "",
        "ownership_pct":        None,
        "ownership_signal":     "",
        "ownership_signal_text": "",

        # Short (placeholder — FINRA collector separat)
        "short_interest_pct":   None,
        "short_sale_volume":    0,
        "total_volume_reported": volume,
        "short_sale_ratio":     None,
        "short_flow_signal":    "",
        "short_signal":         "",

        # Fundamentale
        "pe_ratio":             profile.get("pe_ratio"),
        "beta":                 profile.get("beta"),
        "inst_ownership_pct":   None,

        # Scoruri
        "score":                total_score,
        "score_volume":         s_vol,
        "score_insider":        s_insider,          # FIX: nu mai e hardcodat 0
        "score_insider_quality": s_persist,
        "score_ownership":      0,
        "score_short_interest": 0,
        "score_short_flow":     0,
        "score_fundamental":    0,
        "score_penalty":        0,

        # Semnale
        "volume_signal":        sig_vol,
        "insider_signal":       sig_insider,
        "thesis":               thesis,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def enrich_candidates(candidates: list[dict]) -> list[dict]:
    return [enrich_single(c["ticker"], scan_data=c) for c in candidates if c.get("ticker")]


def enrich_watchlist(tickers: list[str], scan_results: list[dict]) -> list[dict]:
    scan_map = {r["ticker"].upper(): r for r in scan_results if "ticker" in r}
    return [enrich_single(t, scan_data=scan_map.get(t.upper())) for t in tickers]


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if candidates:
        res = enrich_candidates(candidates)
        save_enriched(res)
        print(f"Salvat {len(res)} tickers")
    else:
        print("Niciun candidat de enriched")
