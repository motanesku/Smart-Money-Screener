"""
Universe builder — rulează o dată pe săptămână (duminică 20:00 UTC).
Sursa: FMP /stable/company-screener — 1 singur call, filtrare server-side.
"""
import os
import sys
import time
import requests

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"

MARKET_CAP_MIN = 300_000_000
MARKET_CAP_MAX = 10_000_000_000
AVG_VOLUME_MIN = 200_000
PRICE_MIN      = 5


def build_universe() -> list[dict]:
    print("=== Universe Builder (FMP /stable/company-screener) ===")
    if not FMP_KEY:
        raise ValueError("FMP_KEY nu e setat")

    universe = []
    page     = 0

    while True:
        params = {
            "marketCapMoreThan":    MARKET_CAP_MIN,
            "marketCapLowerThan":   MARKET_CAP_MAX,
            "volumeMoreThan":       AVG_VOLUME_MIN,
            "priceMoreThan":        PRICE_MIN,
            "exchange":             "NYSE,NASDAQ",
            "isActivelyTrading":    "true",
            "limit":                1000,
            "page":                 page,
            "apikey":               FMP_KEY,
        }
        r = requests.get(f"{FMP_BASE}/company-screener", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data:
            break

        for item in data:
            sym = (item.get("symbol") or "").strip()
            if not sym or len(sym) > 5:
                continue
            universe.append({
                "ticker":       sym,
                "company_name": item.get("companyName") or "",
                "exchange":     item.get("exchangeShortName") or "",
                "sector":       item.get("sector") or "",
                "industry":     item.get("industry") or "",
                "market_cap":   int(item.get("marketCap") or 0),
                "avg_volume":   int(item.get("volume") or 0),
            })

        print(f"  Page {page}: {len(data)} tickers | total: {len(universe)}")
        if len(data) < 1000:
            break
        page += 1
        time.sleep(0.5)

    universe.sort(key=lambda x: x["market_cap"], reverse=True)
    print(f"Universe final: {len(universe)} tickers")
    return universe


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import save_universe
    u = build_universe()
    if not u:
        print("EROARE: Universe gol")
        sys.exit(1)
    save_universe(u)
    print(f"Salvat {len(u)} tickers")
    for t in u[:5]:
        print(f"  {t['ticker']:<8} ${t['market_cap']/1e9:.1f}B  {t['sector']}")
