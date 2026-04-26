import os, sys, time
from datetime import date
import requests
import yfinance as yf
from app.db import get_client

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"

def get_profile(ticker: str) -> dict:
    try:
        r = requests.get(f"{FMP_BASE}/profile", params={"symbol": ticker, "apikey": FMP_KEY}, timeout=20)
        data = r.json()
        p = data[0] if isinstance(data, list) and data else {}
        return {"name": p.get("companyName"), "sector": p.get("sector"), "industry": p.get("industry")}
    except: return {}

def get_persistence_count(ticker: str) -> int:
    try:
        res = get_client().table("v_persistence_signals").select("appearance_count").eq("ticker", ticker.upper()).execute()
        return res.data[0]["appearance_count"] if res.data else 0
    except: return 0

def enrich_single(ticker, scan_data=None):
    ticker = ticker.upper()
    print(f"  Enriching {ticker}...")
    profile = get_profile(ticker)
    
    # IMPORT CORECT
    from collectors.edgar import get_insider_data_edgar
    insider = get_insider_data_edgar(ticker)
    
    p_count = get_persistence_count(ticker)
    vol_ratio = scan_data.get("vol_ratio", 0) if scan_data else 0
    
    # Logica Scoring
    score = (insider.get("buys", 0) * 20) + (min(p_count, 3) * 10) + (min(vol_ratio, 5) * 10)
    
    return {
        "ticker": ticker,
        "enrich_date": date.today().isoformat(),
        "company_name": profile.get("name"),
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "vol_ratio": round(vol_ratio, 2),
        "score": min(int(score), 100),
        "top_insider_role": insider.get("top_role")
    }

def enrich_candidates(candidates):
    return [enrich_single(c['ticker'], scan_data=c) for c in candidates if c.get('ticker')]

def enrich_watchlist(tickers, scan_results):
    scan_map = {r['ticker'].upper(): r for r in scan_results if 'ticker' in r}
    return [enrich_single(t, scan_data=scan_map.get(t.upper())) for t in tickers]

if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if candidates:
        res = enrich_candidates(candidates)
        save_enriched(res)
