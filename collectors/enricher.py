"""
Enricher v11 — FMP Profile + SEC EDGAR + Persistence Scoring.
"""
import os, sys, time
from datetime import date, timedelta
import requests
import yfinance as yf
from app.db import get_client # Pentru check persistență

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"

def get_profile(ticker: str) -> dict:
    """FMP /stable/profile — singurul endpoint FMP folosit."""
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
    """Verifică de câte ori a apărut tickerul în scanner în ultimele 14 zile."""
    try:
        res = get_client().table("v_persistence_signals").select("appearance_count").eq("ticker", ticker.upper()).execute()
        return res.data[0]["appearance_count"] if res.data else 0
    except: return 0

def calculate_smart_money_score(data, p_count):
    """Scoring v2: Insider (40p) + Persistență (30p) + Volum (30p)."""
    score = 0
    # Insider Score (bazat pe datele tale din EDGAR/FMP)
    score += data.get('score_insider', 0)
    
    # Persistence Score (NOU)
    if p_count >= 3: score += 30
    elif p_count >= 2: score += 15
    
    # Vol Ratio Bonus
    vr = data.get('vol_ratio', 0)
    if vr > 5: score += 30
    elif vr > 2: score += 15
    
    return min(score, 100)

def enrich_single(ticker, scan_data=None):
    ticker = ticker.upper()
    profile = get_profile(ticker)
    
    # Aici ar veni apelul tău la edgar.py pentru insider data
    # (Presupunem că aduci datele din edgar.get_insider_data_edgar)
    
    p_count = get_persistence_count(ticker)
    
    enriched = {
        "ticker": ticker,
        "enrich_date": date.today().isoformat(),
        "company_name": profile.get("company_name"),
        "sector": profile.get("sector"),
        "vol_ratio": scan_data.get("vol_ratio", 0) if scan_data else 0,
        "score_insider": 0, # Placeholder pt datele din EDGAR
        "score": 0
    }
    
    enriched["score"] = calculate_smart_money_score(enriched, p_count)
    return enriched

def enrich_candidates(candidates: list[dict]) -> list[dict]:
    results = []
    for c in candidates:
        res = enrich_single(c['ticker'], scan_data=c)
        if res: results.append(res)
        time.sleep(0.2) # Politete API
    return results

if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if candidates:
        enriched = enrich_candidates(candidates)
        save_enriched(enriched)
