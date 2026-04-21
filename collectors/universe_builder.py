"""
Construieste universul de tickers o data pe saptamana.
Sursa: FMP /stock/list (1 call gratuit, returneaza toti tickerii)
Filtreaza: mid+small cap $300M-$10B, volum minim, NYSE+NASDAQ only.

Ruleaza via GitHub Actions: duminica la 20:00 UTC
"""
import os
import requests
import sys

FMP_KEY = os.environ.get("FMP_KEY", "demo")
FMP_BASE = "https://financialmodelingprep.com/api/v3"

MARKET_CAP_MIN = 300_000_000      # $300M
MARKET_CAP_MAX = 10_000_000_000   # $10B
AVG_VOLUME_MIN = 200_000           # 200k shares/zi
PRICE_MIN = 5                      # elimina penny stocks
EXCHANGES = {"NYSE", "NASDAQ"}


def fetch_all_tickers() -> list[dict]:
    """
    FMP /stock/list returneaza ~25k tickers intr-un singur call.
    Fiecare are: symbol, name, exchange, price, type
    """
    url = f"{FMP_BASE}/stock/list?apikey={FMP_KEY}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    print(f"FMP: {len(data)} tickers totali descarcati")
    return data


def fetch_market_caps(tickers: list[str]) -> dict[str, dict]:
    """
    FMP /profile/{ticker} are market cap si volum.
    Batch de 50 tickers per call pentru a economisi API calls.
    Returneaza dict: ticker -> {market_cap, avg_volume, sector, industry}
    """
    result = {}
    batch_size = 50
    total_batches = (len(tickers) + batch_size - 1) // batch_size

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        symbols = ",".join(batch)
        url = f"{FMP_BASE}/profile/{symbols}?apikey={FMP_KEY}"
        
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            profiles = r.json()
            
            for p in profiles:
                ticker = p.get("symbol", "")
                if ticker:
                    result[ticker] = {
                        "market_cap": p.get("mktCap", 0) or 0,
                        "avg_volume": p.get("volAvg", 0) or 0,
                        "sector": p.get("sector", ""),
                        "industry": p.get("industry", ""),
                    }
        except Exception as e:
            print(f"Eroare batch {i//batch_size + 1}/{total_batches}: {e}")
            continue
        
        batch_num = i // batch_size + 1
        if batch_num % 10 == 0:
            print(f"  Profile: {batch_num}/{total_batches} batches procesate")

    return result


def build_universe() -> list[dict]:
    print("=== Universe Builder ===")
    
    # Step 1: Lista completa de tickers
    all_tickers = fetch_all_tickers()
    
    # Step 2: Filtru rapid pe exchange si pret (fara API call extra)
    pre_filtered = [
        t for t in all_tickers
        if t.get("exchangeShortName", "").upper() in EXCHANGES
        and t.get("type") == "stock"
        and (t.get("price") or 0) >= PRICE_MIN
    ]
    print(f"Dupa filtru exchange+pret: {len(pre_filtered)} tickers")
    
    # Step 3: Fetch profile pentru market cap si volum
    ticker_symbols = [t["symbol"] for t in pre_filtered]
    print(f"Fetch profile pentru {len(ticker_symbols)} tickers...")
    profiles = fetch_market_caps(ticker_symbols)
    
    # Step 4: Filtru final pe market cap si volum
    universe = []
    for t in pre_filtered:
        sym = t["symbol"]
        profile = profiles.get(sym, {})
        
        mc = profile.get("market_cap", 0)
        vol = profile.get("avg_volume", 0)
        
        if (MARKET_CAP_MIN <= mc <= MARKET_CAP_MAX and vol >= AVG_VOLUME_MIN):
            universe.append({
                "ticker": sym,
                "company_name": t.get("name", ""),
                "exchange": t.get("exchangeShortName", ""),
                "sector": profile.get("sector", ""),
                "industry": profile.get("industry", ""),
                "market_cap": int(mc),
                "avg_volume": int(vol),
            })
    
    universe.sort(key=lambda x: x["market_cap"], reverse=True)
    print(f"Universe final: {len(universe)} tickers")
    return universe


if __name__ == "__main__":
    # Import db doar cand ruleaza ca script (nu in tests)
    sys.path.insert(0, ".")
    from app.db import save_universe
    
    universe = build_universe()
    
    if not universe:
        print("EROARE: Universe gol — verifica FMP_KEY si conexiunea")
        sys.exit(1)
    
    save_universe(universe)
    print(f"Salvat {len(universe)} tickers in Supabase")
    
    # Print sample
    print("\nSample (top 10 dupa market cap):")
    for t in universe[:10]:
        mc_b = t['market_cap'] / 1e9
        print(f"  {t['ticker']:<8} {t['company_name']:<35} ${mc_b:.1f}B  {t['sector']}")
