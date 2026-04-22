"""
Enrich — colecteaza semnale smart money pentru candidatii din scan.
Ruleaza de 2x/zi: 08:45 ET si 16:30 ET.

Surse confirmate gratuite:
  FMP /stable/profile              — market cap, sector, beta, PE, float
  FMP /stable/insider-trading/latest — insider trades recente (filtrate pe ticker)
  SEC EDGAR                        — Form 4 count backup
  yfinance                         — short interest, volume data

FMP calls per run: ~2 x nr_candidati (max 50) = ~100 calls din 250/zi
"""
import os
import sys
import time

import requests
import yfinance as yf

from collectors.edgar import get_insider_transactions_detailed

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"


def fmp_get(endpoint: str, params: dict = {}) -> list | dict:
    """Generic FMP call cu error handling."""
    try:
        p = {**params, "apikey": FMP_KEY}
        r = requests.get(f"{FMP_BASE}/{endpoint}", params=p, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  FMP {endpoint} error: {e}")
        return {}


def get_profile(ticker: str) -> dict:
    """
    FMP /stable/profile — 1 call, returneaza:
    market cap, sector, industry, beta, PE, avg volume, description.
    Confirmat gratuit.
    """
    data = fmp_get("profile", {"symbol": ticker})
    if isinstance(data, list) and data:
        p = data[0]
    elif isinstance(data, dict):
        p = data
    else:
        return {}

    return {
        "sector":           p.get("sector") or "",
        "industry":         p.get("industry") or "",
        "pe_ratio":         p.get("pe") or p.get("peRatio"),
        "market_cap":       int(p.get("mktCap") or p.get("marketCap") or 0),
        "inst_ownership_pct": p.get("institutionalOwnershipPercentage"),
        "beta":             p.get("beta"),
    }


def get_insider_trades_fmp(ticker: str, days_back: int = 90) -> dict:
    """
    FMP /stable/insider-trading/latest filtrat pe symbol.
    Confirmat gratuit. Returneaza tranzactii reale cu valori $.
    """
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days_back)).isoformat()

    data = fmp_get("insider-trading/latest", {
        "symbol": ticker,
        "limit":  50,
    })

    if not isinstance(data, list):
        return {"insider_buys_90d": 0, "insider_buy_value": 0.0, "insider_sells_90d": 0}

    buys      = 0
    buy_value = 0.0
    sells     = 0

    for trade in data:
        trade_date = trade.get("transactionDate") or trade.get("filingDate") or ""
        if trade_date < since:
            continue

        tx_type = (trade.get("transactionType") or trade.get("acquistionOrDisposition") or "").upper()
        shares   = abs(float(trade.get("securitiesTransacted") or trade.get("shares") or 0))
        price    = float(trade.get("price") or trade.get("transactionPrice") or 0)
        value    = shares * price

        if tx_type in ("P", "A", "PURCHASE", "P-PURCHASE", "BUY"):
            buys      += 1
            buy_value += value
        elif tx_type in ("S", "D", "SALE", "S-SALE", "SELL"):
            sells += 1

    return {
        "insider_buys_90d":  buys,
        "insider_buy_value": round(buy_value, 2),
        "insider_sells_90d": sells,
    }


def get_short_interest(ticker: str) -> dict:
    """yfinance pentru short interest — gratuit."""
    try:
        info = yf.Ticker(ticker).info
        si   = info.get("shortPercentOfFloat") or 0
        return {"short_interest_pct": round(si * 100, 2) if si < 1 else round(si, 2)}
    except Exception:
        return {}


def calculate_score(data: dict) -> int:
    score = 0

    # Volume spike
    vol = data.get("vol_ratio") or 1.0
    if vol >= 5:   score += 25
    elif vol >= 3: score += 15
    elif vol >= 2: score += 8

    # Insider buying — semnal cel mai puternic
    buys = data.get("insider_buys_90d") or 0
    val  = data.get("insider_buy_value") or 0
    if val >= 1_000_000:  score += 35
    elif val >= 250_000:  score += 20
    elif buys >= 3:       score += 20
    elif buys >= 1:       score += 10

    # Short interest
    si = data.get("short_interest_pct") or 0
    if 0 < si <= 5:    score += 10
    elif si <= 15:     score += 5
    elif si > 30:      score -= 10

    # Institutional ownership
    inst = data.get("inst_ownership_pct") or 0
    if inst >= 60:   score += 10
    elif inst >= 40: score += 5

    # PE rezonabil
    pe = data.get("pe_ratio") or 0
    if 5 <= pe <= 25:   score += 10
    elif 25 < pe <= 40: score += 5

    return max(0, min(100, score))


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    enriched = []
    total    = len(candidates)
    print(f"Enrich pentru {total} candidati...")
    print(f"FMP calls estimate: ~{total * 2} din 250 disponibile")

    for i, candidate in enumerate(candidates):
        ticker = candidate["ticker"]
        data   = {**candidate}
        print(f"  [{i+1}/{total}] {ticker}")

        # Call 1: FMP profile (sector, PE, market cap, institutional)
        profile = get_profile(ticker)
        data.update(profile)
        time.sleep(0.3)

        # Call 2: FMP insider trades (valori reale in $)
        insider = get_insider_trades_fmp(ticker)
        data.update(insider)
        time.sleep(0.3)

        # Gratuit: yfinance short interest
        si = get_short_interest(ticker)
        data.update(si)

        data["score"] = calculate_score(data)
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
            print(f"  {e['ticker']:<8} score={e['score']}/100 "
                  f"buys={e.get('insider_buys_90d',0)} "
                  f"vol={e.get('vol_ratio',0)}x")
