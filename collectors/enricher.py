"""
Enrich — colecteaza semnale smart money pentru candidatii din scan.
Ruleaza de 2x/zi: 08:45 ET si 16:30 ET.
Compatibil cu surse gratuite si consum moderat de API.
"""
import os
import sys
import time
import requests
import yfinance as yf

FMP_KEY = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"


def fmp_get(endpoint: str, params: dict | None = None) -> list | dict:
    params = params or {}
    try:
        payload = {**params, "apikey": FMP_KEY}
        r = requests.get(f"{FMP_BASE}/{endpoint}", params=payload, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  FMP {endpoint} error: {e}")
        return {}


def get_profile(ticker: str) -> dict:
    data = fmp_get("profile", {"symbol": ticker})
    if isinstance(data, list) and data:
        p = data[0]
    elif isinstance(data, dict):
        p = data
    else:
        return {}

    return {
        "sector": p.get("sector") or "",
        "industry": p.get("industry") or "",
        "pe_ratio": p.get("pe") or p.get("peRatio"),
        "market_cap": int(p.get("mktCap") or p.get("marketCap") or 0),
        "inst_ownership_pct": p.get("institutionalOwnershipPercentage"),
    }


def get_insider_trades_fmp(ticker: str, days_back: int = 90) -> dict:
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days_back)).isoformat()

    data = fmp_get("insider-trading/latest", {
        "symbol": ticker,
        "limit": 50,
    })

    if not isinstance(data, list):
        return {"insider_buys_90d": 0, "insider_buy_value": 0.0, "insider_sells_90d": 0}

    buys = 0
    buy_value = 0.0
    sells = 0

    for trade in data:
        trade_date = trade.get("transactionDate") or trade.get("filingDate") or ""
        if trade_date < since:
            continue

        tx_type = (trade.get("transactionType") or trade.get("acquistionOrDisposition") or "").upper()
        shares = abs(float(trade.get("securitiesTransacted") or trade.get("shares") or 0))
        price = float(trade.get("price") or trade.get("transactionPrice") or 0)
        value = shares * price

        if tx_type in ("P", "A", "PURCHASE", "P-PURCHASE", "BUY"):
            buys += 1
            buy_value += value
        elif tx_type in ("S", "D", "SALE", "S-SALE", "SELL"):
            sells += 1

    return {
        "insider_buys_90d": buys,
        "insider_buy_value": round(buy_value, 2),
        "insider_sells_90d": sells,
    }


def get_short_interest(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        si = info.get("shortPercentOfFloat") or 0
        return {"short_interest_pct": round(si * 100, 2) if si and si < 1 else round(si, 2)}
    except Exception:
        return {"short_interest_pct": None}


def score_volume(vol_ratio: float | int | None) -> tuple[int, str]:
    v = float(vol_ratio or 0)
    if v >= 5:
        return 25, "Extreme volume spike (>5x)"
    if v >= 3:
        return 15, "Strong unusual volume (>3x)"
    if v >= 2:
        return 8, "Unusual volume (>2x)"
    return 0, "Normal volume"


def score_insider(buys: int, buy_value: float, sells: int) -> tuple[int, int, str]:
    score = 0
    penalty = 0

    if buy_value >= 1_000_000:
        score += 35
    elif buy_value >= 250_000:
        score += 20
    elif buys >= 3:
        score += 20
    elif buys >= 1:
        score += 10

    if sells >= 10:
        penalty -= 12
    elif sells >= 5:
        penalty -= 6
    elif sells >= 1:
        penalty -= 2

    if buy_value >= 1_000_000:
        signal = "Strong insider conviction"
    elif buys >= 1:
        signal = "Some insider buying detected"
    elif sells >= 5:
        signal = "Heavy insider selling"
    elif sells >= 1:
        signal = "Some insider selling"
    else:
        signal = "No meaningful insider activity"

    return score, penalty, signal


def score_short_interest(si: float | None) -> tuple[int, str]:
    if si is None:
        return 0, "Short interest unavailable"
    s = float(si)
    if 0 < s <= 5:
        return 10, "Low short interest (<5%)"
    if s <= 15:
        return 5, "Moderate short interest (5-15%)"
    if s <= 25:
        return 0, "High short interest (watch risk)"
    return -10, "Very high short interest (>25%)"


def score_fundamental(pe_ratio: float | None, inst_ownership_pct: float | None) -> tuple[int, str]:
    score = 0
    notes = []

    pe = float(pe_ratio or 0)
    inst = float(inst_ownership_pct or 0)

    if 5 <= pe <= 25:
        score += 10
        notes.append("P/E in reasonable range")
    elif 25 < pe <= 40:
        score += 5
        notes.append("P/E acceptable but not cheap")
    elif pe > 40:
        notes.append("P/E elevated")

    if inst >= 60:
        score += 10
        notes.append("Strong institutional ownership")
    elif inst >= 40:
        score += 5
        notes.append("Decent institutional ownership")

    return score, "; ".join(notes) if notes else "Limited fundamental support"


def build_thesis(data: dict) -> str:
    parts = []
    if (data.get("score_volume") or 0) >= 15:
        parts.append("volume unusual")
    if (data.get("score_insider") or 0) >= 20:
        parts.append("insider buying meaningful")
    if (data.get("score_short_interest") or 0) > 0:
        parts.append("short interest manageable")
    if (data.get("score_fundamental") or 0) >= 10:
        parts.append("fundamentals acceptable")
    if (data.get("score_penalty") or 0) < 0:
        parts.append("but insider selling tempers conviction")

    if not parts:
        return "Weak setup. Mostly watchlist candidate, not high-conviction."

    return ", ".join(parts).capitalize() + "."


def calculate_scores(data: dict) -> dict:
    vol_score, vol_signal = score_volume(data.get("vol_ratio"))
    insider_score, penalty, insider_signal = score_insider(
        int(data.get("insider_buys_90d") or 0),
        float(data.get("insider_buy_value") or 0),
        int(data.get("insider_sells_90d") or 0),
    )
    short_score, short_signal = score_short_interest(data.get("short_interest_pct"))
    fundamental_score, _ = score_fundamental(data.get("pe_ratio"), data.get("inst_ownership_pct"))

    total = vol_score + insider_score + short_score + fundamental_score + penalty
    total = max(0, min(100, total))

    data["score_volume"] = vol_score
    data["score_insider"] = insider_score
    data["score_short_interest"] = short_score
    data["score_fundamental"] = fundamental_score
    data["score_penalty"] = penalty
    data["score"] = total
    data["volume_signal"] = vol_signal
    data["insider_signal"] = insider_signal
    data["short_signal"] = short_signal
    data["thesis"] = build_thesis(data)
    return data


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    enriched = []
    total = len(candidates)
    print(f"Enrich pentru {total} candidati...")
    print(f"FMP calls estimate: ~{total * 2} din 250 disponibile")

    for i, candidate in enumerate(candidates):
        ticker = candidate["ticker"]
        data = {**candidate}
        print(f"  [{i+1}/{total}] {ticker}")

        profile = get_profile(ticker)
        data.update(profile)
        time.sleep(0.25)

        insider = get_insider_trades_fmp(ticker)
        data.update(insider)
        time.sleep(0.25)

        data.update(get_short_interest(ticker))
        data = calculate_scores(data)
        enriched.append(data)

    enriched.sort(key=lambda x: x["score"], reverse=True)
    if enriched:
        top = enriched[0]
        print(f"\nTop scorer: {top['ticker']} = {top['score']}/100")
    return enriched


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched

    candidates = get_scan_results(days_back=1)
    if not candidates:
        print("Niciun candidat azi")
        sys.exit(0)

    enriched = enrich_candidates(candidates)
    if enriched:
        save_enriched(enriched)
        print(f"\nSalvat {len(enriched)} tickers in Supabase")
        for e in enriched[:10]:
            print(
                f"  {e['ticker']:<8} score={e['score']}/100 "
                f"vol={e.get('score_volume',0)} insider={e.get('score_insider',0)} "
                f"short={e.get('score_short_interest',0)} pen={e.get('score_penalty',0)}"
            )
