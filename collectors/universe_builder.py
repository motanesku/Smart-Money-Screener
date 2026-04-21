"""
Construieste universul de tickers o data pe saptamana.
Sursa: FMP /stable/ endpoints (noul API format)
Filtreaza: mid+small cap $300M-$10B, volum minim, NYSE+NASDAQ only.

Ruleaza via GitHub Actions: duminica la 20:00 UTC
"""
import os
import sys
import requests
import time

FMP_KEY = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"

MARKET_CAP_MIN = 300_000_000
MARKET_CAP_MAX = 10_000_000_000
AVG_VOLUME_MIN  = 200_000
PRICE_MIN       = 5
EXCHANGES       = {"NYSE", "NASDAQ"}


def fetch_universe_via_screener() -> list[dict]:
    """
    FMP /stable/stock-screener permite filtrare directa pe market cap,
    volum, exchange — returneaza exact ce avem nevoie intr-un numar mic de calls.
    Pagineaza cate 1000 tickers per call.
    """
    all_tickers = []
    page = 0

    while True:
        params = {
            "marketCapMoreThan": MARKET_CAP_MIN,
            "marketCapLowerThan": MARKET_CAP_MAX,
            "volumeMoreThan": AVG_VOLUME_MIN,
            "priceMoreThan": PRICE_MIN,
            "exchange": "NYSE,NASDAQ",
            "isActivelyTrading": "true",
            "limit": 1000,
            "page": page,
            "apikey": FMP_KEY,
        }

        url = f"{FMP_BASE}/stock-screener"
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        if not data:
            break

        for item in data:
            all_tickers.append({
                "ticker":       item.get("symbol", ""),
                "company_name": item.get("companyName", ""),
                "exchange":     item.get("exchangeShortName", ""),
                "sector":       item.get("sector", "") or "",
                "industry":     item.get("industry", "") or "",
                "market_cap":   int(item.get("marketCap", 0) or 0),
                "avg_volume":   int(item.get("volume", 0) or 0),
            })

        print(f"  Page {page}: {len(data)} tickers, total acum: {len(all_tickers)}")

        if len(data) < 1000:
            break

        page += 1
        time.sleep(0.5)  # politete fata de API

    return all_tickers


def build_universe() -> list[dict]:
    print("=== Universe Builder (FMP /stable/stock-screener) ===")

    if not FMP_KEY:
        raise ValueError("FMP_KEY nu e setat in environment")

    universe = fetch_universe_via_screener()

    # Elimina tickers fara symbol valid
    universe = [u for u in universe if u["ticker"] and len(u["ticker"]) <= 5]
    universe.sort(key=lambda x: x["market_cap"], reverse=True)

    print(f"\nUniverse final: {len(universe)} tickers")
    return universe


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import save_universe

    universe = build_universe()

    if not universe:
        print("EROARE: Universe gol — verifica FMP_KEY")
        sys.exit(1)

    save_universe(universe)
    print(f"Salvat {len(universe)} tickers in Supabase")

    print("\nSample (top 10 dupa market cap):")
    for t in universe[:10]:
        mc_b = t["market_cap"] / 1e9
        print(f"  {t['ticker']:<8} {t['company_name']:<35} ${mc_b:.1f}B  {t['sector']}")
