"""
Earnings detection via SEC EDGAR 8-K filings.
Detectează dacă o companie a raportat earnings recent (Item 2.02 — Results of Operations)
sau a publicat guidance (Item 7.01 — Reg FD Disclosure).
"""
import requests
import re
from datetime import datetime, timedelta
from app.utils.logger import log_warn

SEC_HEADERS = {
    "User-Agent": "smartmoney/1.0 danut.fagadau@gmail.com",
}

# Item codes pentru earnings
EARNINGS_REPORTED_ITEMS = ["2.02"]  # Results of Operations
GUIDANCE_ITEMS = ["7.01"]            # Regulation FD — guidance, guidance changes


def get_earnings_from_edgar(ticker: str) -> dict:
    """
    Detectează 8-K recente pentru un ticker.
    - Item 2.02: earnings tocmai raportate (ultimele 3 zile)
    - Item 7.01: guidance announcements (ultimele 5 zile)

    Return: {
        "earnings_date":    "YYYY-MM-DD" | None,
        "earnings_source":  "sec_edgar_8k" | None,
        "days_to_earnings": 0 (raportat azi) | 1 (ieri) | None (necunoscut)
    }
    """
    ticker = (ticker or "").upper()
    if not ticker:
        return {"earnings_date": None, "earnings_source": None, "days_to_earnings": None}

    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d")

        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q":         f'"{ticker}"',
            "forms":     "8-K",
            "dateRange": "custom",
            "startdt":   start_date,
            "enddt":     today,
        }

        resp = requests.get(url, headers=SEC_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            return {"earnings_date": None, "earnings_source": None, "days_to_earnings": None}

        # Caută 8-K cu ticker-ul nostru
        for hit in hits:
            source = hit.get("_source", {})
            display_names = source.get("display_names", [])

            # Extrage ticker din format: "APPLE INC  (AAPL)  (CIK 0000320193)"
            filing_ticker = None
            for name in display_names:
                match = re.search(r'\(([A-Z]{1,5})\)\s+\(CIK', name)
                if match:
                    filing_ticker = match.group(1)
                    break

            if filing_ticker != ticker:
                continue

            # Găsit match — extrage metadatele
            filing_date = source.get("filing_date", "")
            items = source.get("items", []) or []

            # Verifică dacă e earnings report (Item 2.02)
            if any(item.startswith("2.02") for item in items):
                days_ago = _days_between(filing_date, today)
                return {
                    "earnings_date": filing_date,
                    "earnings_source": "sec_edgar_8k",
                    "days_to_earnings": 0 if days_ago == 0 else days_ago,
                }

            # Fallback: guidance (Item 7.01)
            if any(item.startswith("7.01") for item in items):
                return {
                    "earnings_date": filing_date,
                    "earnings_source": "sec_edgar_8k_guidance",
                    "days_to_earnings": None,
                }

        return {"earnings_date": None, "earnings_source": None, "days_to_earnings": None}

    except Exception as e:
        log_warn(f"[Earnings8K] {ticker} fetch failed: {e}")
        return {"earnings_date": None, "earnings_source": None, "days_to_earnings": None}


def _days_between(date_str: str, today_str: str) -> int:
    """
    Calculează diferența în zile între două date ISO.
    Returnează 0 pentru azi, 1 pentru ieri, etc.
    """
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.strptime(today_str, "%Y-%m-%d")
        delta = (today - d).days
        return max(0, delta)
    except:
        return 0
