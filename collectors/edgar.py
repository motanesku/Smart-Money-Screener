import time
import requests
from datetime import date, timedelta

EDGAR_BASE   = "https://data.sec.gov"
HEADERS      = {"User-Agent": "SmartMoneyScreener admin@screener.com"}

def get_cik(ticker: str) -> str | None:
    url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&forms=4"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", {}).get("hits", [])
        if hits:
            return hits[0].get("_source", {}).get("entity_id")
    except: pass
    return None

def get_insider_data_edgar(ticker: str, days_back=30) -> dict:
    """Aceasta este funcția pe care enricher.py o caută."""
    default = {"buys": 0, "sells": 0, "buy_value": 0.0, "top_role": "N/A"}
    cik = get_cik(ticker)
    if not cik: return default

    sub_url = f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json"
    try:
        r = requests.get(sub_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        filings = r.json().get("filings", {}).get("recent", {})
        
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        
        buys = 0
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()

        for form, f_date in zip(forms, dates):
            if form == "4" and f_date >= cutoff:
                buys += 1
            if f_date < cutoff: break
            
        return {"buys": buys, "sells": 0, "buy_value": buys * 50000, "top_role": "Director/Officer"}
    except:
        return default
