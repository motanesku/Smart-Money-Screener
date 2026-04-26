"""
Enricher v11 — FULL CODE
Combină FMP Profile, SEC Insider Data și Persistence Scoring.
"""
import os, sys, time
from datetime import date, timedelta
import requests
import yfinance as yf
from app.db import get_client

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"

def get_profile(ticker: str) -> dict:
    try:
        r = requests.get(f"{FMP_BASE}/profile",
                         params={"symbol": ticker, "apikey": FMP_KEY}, timeout=20)
        r.raise_for_status()
        data = r.json()
        p = data[0] if isinstance(data, list) and data else {}
        return {
            "company_name": p.get("companyName") or "",
            "sector":       p.get("sector") or "",
            "industry":     p.get("industry") or "",
            "description":  p.get("description") or ""
        }
    except: return {}

def get_persistence_count(ticker: str) -> int:
    """Verifică istoricul din view-ul SQL v_persistence_signals."""
    try:
        res = get_client().table("v_persistence_signals").select("appearance_count").eq("ticker", ticker.upper()).execute()
        return res.data[0]["appearance_count"] if res.data else 0
    except: return 0

def calculate_smart_money_score(data, p_count):
    score = 0
    # 1. Insider Score (din datele colectate anterior)
    score += data.get('score_insider', 0)
    
    # 2. Persistence Score (0-30p)
    if p_count >= 3: score += 30
    elif p_count >= 2: score += 15
    
    # 3. Vol Ratio Bonus (0-30p)
    vr = data.get('vol_ratio', 0)
    if vr > 5: score += 30
    elif vr > 2: score += 15
    
    return min(score, 100)

def enrich_single(ticker, scan_data=None):
    ticker = ticker.upper()
    profile = get_profile(ticker)
    
    # Importă logica de insider din edgar.py-ul tău
    from collectors.edgar import get_insider_data_edgar
    insider = get_insider_data_edgar(ticker)
    
    p_count = get_persistence_count(ticker)
    
    data = {
        "ticker": ticker,
        "enrich_date": date.today().isoformat(),
        "company_name": profile.get("company_name"),
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "vol_ratio": scan_data.get("vol_ratio", 0) if scan_data else 0,
        "score_insider": insider.get("buys", 0) * 10, # Logica ta de scor insider
        "top_insider_role": insider.get("top_role", "")
    }
    
    data["score"] = calculate_smart_money_score(data, p_count)
    return data

def enrich_candidates(candidates: list[dict]) -> list[dict]:
    results = []
    for c in candidates:
        res = enrich_single(c['ticker'], scan_data=c)
        if res: results.append(res)
        time.sleep(0.2)
    return results

if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if candidates:
        enriched = enrich_candidates(candidates)
        save_enriched(enriched)
