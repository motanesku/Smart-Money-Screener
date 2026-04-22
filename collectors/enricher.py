"""
Enrich — colectează semnale smart money pentru candidații din scan.
Rulează de 2x/zi: 08:45 ET și 16:30 ET.

Surse și distribuție calls:
  SEC EDGAR  — insider Form 4        — gratuit, fără limite
  yfinance   — price, P/E, float     — gratuit, fără limite
  Finnhub    — institutional own %   — 60 calls/min free tier
  FMP        — NU e folosit la enrich (economisit pentru universe)
"""
import os
import sys
import time

import finnhub
import yfinance as yf

from collectors.edgar import get_insider_transactions_detailed

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")


def get_finnhub_client():
    if not FINNHUB_KEY:
        raise ValueError("FINNHUB_KEY nu e setat")
    return finnhub.Client(api_key=FINNHUB_KEY)


def get_yfinance_data(ticker: str) -> dict:
    """P/E, short interest, float — gratuit via yfinance."""
    try:
        info = yf.Ticker(ticker).info
        return {
            "pe_ratio":           info.get("trailingPE"),
            "short_interest_pct": info.get("shortPercentOfFloat"),
        }
    except Exception:
        return {}


def get_institutional_ownership(client, ticker: str) -> dict:
    """Institutional ownership % via Finnhub — 1 call per ticker."""
    try:
        data   = client.company_basic_financials(ticker, "all")
        metric = data.get("metric") or {}
        return {
            "inst_ownership_pct": metric.get("institutionalOwnershipPercentage"),
        }
    except Exception:
        return {}


def calculate_score(data: dict) -> int:
    """Score 0-100 bazat pe semnalele disponibile."""
    score = 0

    # Volume spike
    vol = data.get("vol_ratio", 1.0) or 1.0
    if vol >= 5:   score += 25
    elif vol >= 3: score += 15
    elif vol >= 2: score += 8

    # Insider buying (Form 4 count ca proxy)
    buys = data.get("insider_buys_90d", 0) or 0
    val  = data.get("insider_buy_value", 0) or 0
    if val >= 1_000_000:  score += 35
    elif val >= 250_000:  score += 20
    elif buys >= 3:       score += 25
    elif buys >= 1:       score += 12

    # Short interest
    si = data.get("short_interest_pct", 0) or 0
    if 0 < si <= 0.05:   score += 10
    elif si <= 0.15:     score += 5
    elif si > 0.30:      score -= 10

    # Institutional ownership
    inst = data.get("inst_ownership_pct", 0) or 0
    if inst >= 60:   score += 10
    elif inst >= 40: score += 5

    # Valuation
    pe = data.get("pe_ratio", 0) or 0
    if 5 <= pe <= 25:   score += 10
    elif 25 < pe <= 40: score += 5

    return max(0, min(100, score))


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    try:
        fh_client = get_finnhub_client()
    except ValueError:
        fh_client = None
        print("WARNING: Finnhub key lipsă — institutional ownership va fi None")

    enriched = []
    total    = len(candidates)
    print(f"Enrich pentru {total} candidați...")

    for i, candidate in enumerate(candidates):
        ticker = candidate["ticker"]
        data   = {**candidate}
        print(f"  [{i+1}/{total}] {ticker}")

        # 1. SEC EDGAR — insider Form 4 (gratuit)
        insider = get_insider_transactions_detailed(ticker)
        data.update(insider)
        time.sleep(0.15)   # politete față de SEC (max ~6 req/sec)

        # 2. yfinance — P/E, short interest (gratuit)
        yf_data = get_yfinance_data(ticker)
        data.update(yf_data)

        # 3. Finnhub — institutional ownership (1 call, ~1/sec)
        if fh_client:
            inst = get_institutional_ownership(fh_client, ticker)
            data.update(inst)
            time.sleep(1.1)   # Finnhub free: 60 calls/min

        data["score"] = calculate_score(data)
        enriched.append(data)

    enriched.sort(key=lambda x: x["score"], reverse=True)
    if enriched:
        print(f"\nTop scorer: {enriched[0]['ticker']} = {enriched[0]['score']}/100")
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
        print(f"\nSalvat {len(enriched)} tickers în Supabase")
        print("\nTop 10:")
        for e in enriched[:10]:
            print(f"  {e['ticker']:<8} score={e['score']}/100 "
                  f"buys={e.get('insider_buys_90d',0)} "
                  f"vol={e.get('vol_ratio',0)}x")
