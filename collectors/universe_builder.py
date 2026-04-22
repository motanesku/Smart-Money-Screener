"""
Universe builder — rulează o dată pe săptămână.

Surse:
  - FMP: biggest-gainers, biggest-losers, most-actives
  - Wikipedia: S&P400 + S&P600

Obiectiv:
  - univers mic, relevant, free
  - fără să consume call-urile inutil
"""
import os
import sys
import time
import requests
import pandas as pd

FMP_KEY = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"

HEADERS = {
    "User-Agent": "SmartMoneyScreener/1.0 (contact: admin@example.com)"
}


def fetch_fmp(endpoint: str) -> list[dict]:
    url = f"{FMP_BASE}/{endpoint}"
    r = requests.get(url, params={"apikey": FMP_KEY}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def fetch_active_tickers() -> list[dict]:
    results = {}

    for endpoint, label in [
        ("biggest-gainers", "gainers"),
        ("biggest-losers", "losers"),
        ("most-actives", "actives"),
    ]:
        try:
            data = fetch_fmp(endpoint)
            for item in data:
                sym = (item.get("symbol") or item.get("ticker") or "").strip().upper()
                if not sym or len(sym) > 6 or "." in sym:
                    continue

                if sym not in results:
                    results[sym] = {
                        "ticker": sym,
                        "company_name": item.get("name") or item.get("companyName") or "",
                        "exchange": item.get("exchange") or "",
                        "sector": item.get("sector") or "",
                        "industry": item.get("industry") or "",
                        "market_cap": int(item.get("marketCap") or 0),
                        "avg_volume_20d": int(item.get("volume") or 0),
                        "sources": [],
                    }

                results[sym]["sources"].append(label)

            print(f"  {endpoint}: {len(data)} tickers")
            time.sleep(0.4)

        except Exception as e:
            print(f"  {endpoint} EROARE: {e}")

    return list(results.values())


def fetch_table_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def extract_tickers_from_wikipedia(url: str) -> list[str]:
    html = fetch_table_html(url)
    tables = pd.read_html(html, flavor="lxml")
    df = tables[0]

    col = next(
        (
            c for c in df.columns
            if any(k in str(c).lower() for k in ["ticker", "symbol"])
        ),
        df.columns[0]
    )

    tickers = (
        df[col]
        .astype(str)
        .str.strip()
        .str.replace(".", "-", regex=False)
        .tolist()
    )
    return [t for t in tickers if t and t.lower() != "nan" and len(t) <= 6]


def fetch_sp_midsmall() -> list[str]:
    sources = [
        ("S&P400", "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"),
        ("S&P600", "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"),
    ]

    tickers = []
    for name, url in sources:
        try:
            t = extract_tickers_from_wikipedia(url)
            tickers.extend(t)
            print(f"  {name}: {len(t)} tickers")
            time.sleep(0.4)
        except Exception as e:
            print(f"  {name} EROARE: {e}")

    seen = set()
    unique = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique


def build_universe() -> list[dict]:
    print("=== Universe Builder ===")
    if not FMP_KEY:
        raise ValueError("FMP_KEY nu e setat")

    print("Step 1: FMP gainers + losers + actives...")
    active = fetch_active_tickers()
    active_symbols = {t["ticker"] for t in active}
    print(f"  Total activi: {len(active)}")

    print("Step 2: Wikipedia S&P400 + S&P600...")
    sp_tickers = fetch_sp_midsmall()

    universe = list(active)

    for ticker in sp_tickers:
        if ticker not in active_symbols:
            universe.append({
                "ticker": ticker,
                "company_name": "",
                "exchange": "",
                "sector": "",
                "industry": "",
                "market_cap": 0,
                "avg_volume_20d": 0,
            })

    for u in universe:
        u.pop("sources", None)

    universe.sort(key=lambda x: x["market_cap"], reverse=True)

    print(f"\nUniverse final: {len(universe)} tickers")
    return universe


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import save_universe

    universe = build_universe()
    if not universe:
        print("EROARE: Universe gol")
        sys.exit(1)

    save_universe(universe)
    print(f"Salvat {len(universe)} tickers in Supabase")
    for t in universe[:5]:
        mc = (t["market_cap"] or 0) / 1e9
        print(f"  {t['ticker']:<8} ${mc:.1f}B  vol={int(t['avg_volume_20d'] or 0):,}")
