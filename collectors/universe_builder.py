"""
Universe builder — rulează o dată pe săptămână (duminică 20:00 UTC).

Strategie NOUĂ după testare endpoint-uri free FMP:
  - /stable/biggest-gainers   → tickers cu miscare mare
  - /stable/biggest-losers    → tickers cu miscare mare
  - /stable/most-actives      → tickers cu volum mare
  + Wikipedia S&P400/S&P600   → mid/small cap base list

Combinatia acestora acopera exact universul relevant:
tickers cu activitate reala, nu o lista statica de 8000.

FMP calls: 3 (din 250/zi) — rulat 1x/saptamana deci ~0.4 calls/zi medie.
"""
import os
import sys
import time
import requests
import pandas as pd

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"


def fetch_fmp(endpoint: str) -> list[dict]:
    """Fetch generic FMP endpoint."""
    url = f"{FMP_BASE}/{endpoint}"
    r   = requests.get(url, params={"apikey": FMP_KEY}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    return []


def fetch_active_tickers() -> list[dict]:
    """
    Combina gainers + losers + most-actives din FMP.
    Acestia sunt tickerii cu miscare reala — exact ce ne intereseaza.
    3 call-uri FMP.
    """
    results = {}

    for endpoint, label in [
        ("biggest-gainers", "gainers"),
        ("biggest-losers",  "losers"),
        ("most-actives",    "actives"),
    ]:
        try:
            data = fetch_fmp(endpoint)
            for item in data:
                sym = (item.get("symbol") or item.get("ticker") or "").strip().upper()
                if not sym or len(sym) > 5 or "." in sym:
                    continue
                if sym not in results:
                    results[sym] = {
                        "ticker":       sym,
                        "company_name": item.get("name") or item.get("companyName") or "",
                        "exchange":     "",
                        "sector":       "",
                        "industry":     "",
                        "market_cap":   int(item.get("marketCap") or 0),
                        "avg_volume":   int(item.get("volume") or 0),
                        "sources":      [],
                    }
                results[sym]["sources"].append(label)
            print(f"  {endpoint}: {len(data)} tickers")
            time.sleep(0.3)
        except Exception as e:
            print(f"  {endpoint} EROARE: {e}")

    return list(results.values())


def fetch_sp_midsmall() -> list[str]:
    """
    Wikipedia S&P400 + S&P600 pentru mid/small cap base.
    Fara API key. Completeaza ce lipseste din gainers/losers/actives.
    """
    sources = [
        ("S&P400", "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"),
        ("S&P600", "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"),
        ("S&P500", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"),
    ]
    tickers = []
    for name, url in sources:
        try:
            tables = pd.read_html(url, flavor="lxml")
            df     = tables[0]
            col    = next(
                (c for c in df.columns
                 if any(k in str(c) for k in ["Ticker","Symbol","ticker","symbol"])),
                df.columns[0]
            )
            t = (
                df[col].astype(str).str.strip()
                .str.replace(".", "-", regex=False).tolist()
            )
            t = [x for x in t if x and x != "nan" and len(x) <= 6]
            tickers.extend(t)
            print(f"  {name}: {len(t)} tickers")
        except Exception as e:
            print(f"  {name} EROARE: {e}")
    seen, unique = set(), []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def build_universe() -> list[dict]:
    print("=== Universe Builder ===")
    if not FMP_KEY:
        raise ValueError("FMP_KEY nu e setat")

    # Step 1: tickers activi din FMP (3 calls)
    print("Step 1: FMP gainers + losers + actives...")
    active = fetch_active_tickers()
    active_symbols = {t["ticker"] for t in active}
    print(f"  Total activi: {len(active)}")

    # Step 2: S&P400 + S&P600 de pe Wikipedia
    print("Step 2: Wikipedia S&P400 + S&P600...")
    sp_tickers = fetch_sp_midsmall()

    # Step 3: Combina — adauga din S&P ce nu e deja in active
    universe = list(active)
    for ticker in sp_tickers:
        if ticker not in active_symbols:
            universe.append({
                "ticker":       ticker,
                "company_name": "",
                "exchange":     "",
                "sector":       "",
                "industry":     "",
                "market_cap":   0,
                "avg_volume":   0,
            })

    # Curata "sources" din dict inainte de salvare
    for u in universe:
        u.pop("sources", None)

    # Sorteaza: mai intai cei cu market cap cunoscut
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
        mc = t["market_cap"] / 1e9 if t["market_cap"] else 0
        print(f"  {t['ticker']:<8} ${mc:.1f}B  vol={t['avg_volume']:,}")
