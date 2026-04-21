"""
Enrich: colecteaza semnale smart money pentru candidatii din scan.
Ruleaza dupa scan (08:30 ET) si dupa inchiderea pietei (16:30 ET).

Surse:
- Finnhub: insider transactions, basic financials
- SEC EDGAR: Form 4 direct (backup/verificare)

Rate limit Finnhub free: 60 calls/min
Strategie: 2 calls per ticker + sleep intre batches
"""
import os
import sys
import time
from datetime import date, timedelta

import finnhub
import requests


FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")
CALLS_PER_TICKER = 2
CALLS_PER_MINUTE = 55       # 55 in loc de 60 — marja de siguranta
SLEEP_BETWEEN = CALLS_PER_TICKER / CALLS_PER_MINUTE * 60  # ~2.2 sec


def get_finnhub_client():
    if not FINNHUB_KEY:
        raise ValueError("FINNHUB_KEY nu e setat in environment")
    return finnhub.Client(api_key=FINNHUB_KEY)


def get_insider_data(client, ticker: str, days_back: int = 90) -> dict:
    """
    Finnhub /stock/insider-transactions
    Returneaza cumparaturi/vanzari insider din ultimele N zile.
    """
    since = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    today = date.today().strftime("%Y-%m-%d")

    try:
        data = client.stock_insider_transactions(
            symbol=ticker,
            _from=since,
            to=today
        )
        transactions = data.get("data") or []
    except Exception as e:
        print(f"  [{ticker}] Insider error: {e}")
        return {"insider_buys_90d": 0, "insider_buy_value": 0.0, "insider_sells_90d": 0}

    buys = [
        t for t in transactions
        if t.get("transactionType") in ("P-Purchase", "A-Award")
        and (t.get("share") or 0) > 0
    ]
    sells = [
        t for t in transactions
        if t.get("transactionType") == "S-Sale"
    ]

    buy_value = sum(
        (t.get("share") or 0) * (t.get("transactionPrice") or 0)
        for t in buys
    )

    return {
        "insider_buys_90d": len(buys),
        "insider_buy_value": round(buy_value, 2),
        "insider_sells_90d": len(sells),
    }


def get_basic_financials(client, ticker: str) -> dict:
    """
    Finnhub /stock/metric
    Returneaza P/E, short interest, institutional ownership.
    """
    try:
        data = client.company_basic_financials(ticker, "all")
        m = data.get("metric") or {}
    except Exception as e:
        print(f"  [{ticker}] Financials error: {e}")
        return {}

    return {
        "pe_ratio": m.get("peBasicExclExtraTTM"),
        "short_interest_pct": m.get("shortInterestPercent"),
        "inst_ownership_pct": m.get("institutionalOwnershipPercentage"),
    }


def calculate_score(data: dict) -> int:
    """
    Score 0-100 bazat pe semnalele disponibile.
    Ponderile sunt deliberat simple pentru MVP — ajusteaza dupa testare.
    """
    score = 0

    # Volume spike (vine din scan, confirmare)
    vol_ratio = data.get("vol_ratio", 1.0)
    if vol_ratio >= 5:
        score += 25
    elif vol_ratio >= 3:
        score += 15
    elif vol_ratio >= 2:
        score += 8

    # Insider buying (semnal cel mai puternic)
    buy_value = data.get("insider_buy_value", 0) or 0
    buys = data.get("insider_buys_90d", 0) or 0
    if buy_value >= 1_000_000:    # $1M+ insider buy
        score += 35
    elif buy_value >= 250_000:    # $250k+
        score += 20
    elif buys >= 2:               # cel putin 2 cumparaturi
        score += 10

    # Short interest scazut = mai putin risc squeeze invers
    si = data.get("short_interest_pct", 0) or 0
    if 0 < si <= 5:
        score += 10
    elif 5 < si <= 15:
        score += 5
    elif si > 30:
        score -= 10  # risc mare

    # Institutional ownership in crestere (semnal acumulare)
    inst = data.get("inst_ownership_pct", 0) or 0
    if inst >= 60:
        score += 10
    elif inst >= 40:
        score += 5

    # Valuation rezonabila
    pe = data.get("pe_ratio", 0) or 0
    if 5 <= pe <= 25:
        score += 10
    elif 25 < pe <= 40:
        score += 5

    return max(0, min(100, score))


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        print("Niciun candidat de enriched")
        return []

    client = get_finnhub_client()
    enriched = []
    total = len(candidates)

    print(f"Enrich pentru {total} candidati...")
    print(f"Estimated time: ~{int(total * SLEEP_BETWEEN / 60)} minute")

    for i, candidate in enumerate(candidates):
        ticker = candidate["ticker"]
        print(f"  [{i+1}/{total}] {ticker}")

        data = {**candidate}

        # Call 1: insider transactions
        insider = get_insider_data(client, ticker)
        data.update(insider)
        time.sleep(SLEEP_BETWEEN / 2)

        # Call 2: basic financials
        financials = get_basic_financials(client, ticker)
        data.update(financials)
        time.sleep(SLEEP_BETWEEN / 2)

        # Score final
        data["score"] = calculate_score(data)

        enriched.append(data)

        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{total} done")

    enriched.sort(key=lambda x: x["score"], reverse=True)
    print(f"\nEnrich complet. Top scorer: {enriched[0]['ticker']} = {enriched[0]['score']}/100")
    return enriched


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched

    candidates = get_scan_results(days_back=1)

    if not candidates:
        print("Niciun candidat in DB pentru azi — ruleaza scanner.py primul")
        sys.exit(0)

    print(f"Candidati din scan: {len(candidates)}")
    enriched = enrich_candidates(candidates)

    if enriched:
        save_enriched(enriched)
        print(f"\nSalvat {len(enriched)} tickers enriched in Supabase")
        print("\nTop 10 dupa score:")
        for e in enriched[:10]:
            print(f"  {e['ticker']:<8} score={e['score']}/100  "
                  f"buys={e.get('insider_buys_90d',0)}  "
                  f"vol={e.get('vol_ratio',0)}x")
