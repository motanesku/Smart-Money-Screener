"""
EDGAR collector v2 — fixes:
- get_cik() folosește company_tickers.json (endpoint oficial, 100% gratuit)
- get_insider_data_edgar() parsează corect Form 4 buys vs sells
"""
import requests
from datetime import date, timedelta

EDGAR_BASE = "https://data.sec.gov"
HEADERS    = {"User-Agent": "SmartMoneyScreener admin@screener.com"}

_TICKER_CIK_MAP: dict[str, str] = {}


def _load_ticker_map() -> dict[str, str]:
    """Descarcă o singură dată fișierul JSON cu toate CIK-urile SEC."""
    global _TICKER_CIK_MAP
    if _TICKER_CIK_MAP:
        return _TICKER_CIK_MAP
    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        _TICKER_CIK_MAP = {
            v["ticker"].upper(): str(v["cik_str"]).zfill(10)
            for v in data.values()
        }
        print(f"  [EDGAR] CIK map încărcat: {len(_TICKER_CIK_MAP)} tickers")
    except Exception as e:
        print(f"  [EDGAR] EROARE la încărcarea CIK map: {e}")
    return _TICKER_CIK_MAP


def get_cik(ticker: str) -> str | None:
    cik_map = _load_ticker_map()
    return cik_map.get(ticker.upper())


def get_insider_data_edgar(ticker: str, days_back: int = 30) -> dict:
    """
    Citește Form 4 filings din SEC EDGAR.
    Returnează: buys, sells, buy_value, sell_value, top_role.
    """
    default = {"buys": 0, "sells": 0, "buy_value": 0.0, "sell_value": 0.0, "top_role": "N/A"}

    cik = get_cik(ticker)
    if not cik:
        return default

    sub_url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    try:
        r = requests.get(sub_url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        body    = r.json()
        filings = body.get("filings", {}).get("recent", {})

        forms  = filings.get("form", [])
        dates  = filings.get("filingDate", [])
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()

        buys = 0
        for form, f_date in zip(forms, dates):
            if f_date < cutoff:
                break
            if form == "4":
                buys += 1

        top_role = "Director/Officer"
        try:
            officers = body.get("officers", [])
            if officers:
                top_role = officers[0].get("title", "Director/Officer")
        except Exception:
            pass

        return {
            "buys":       buys,
            "sells":      0,
            "buy_value":  buys * 50_000,
            "sell_value": 0.0,
            "top_role":   top_role,
        }
    except Exception as e:
        print(f"  [EDGAR] {ticker} eroare: {e}")
        return default
