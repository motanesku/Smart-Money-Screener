"""
SIC code enrichment via SEC EDGAR.
Descarcă numeric SIC codes + descriptions pentru identificare industrială.
"""
import requests
import time
def log_warn(msg): print(msg)

# Cache in-memory per proces
_sic_cache: dict[str, tuple[int, str] | None] = {}
_cik_map: dict[str, str] | None = None

SEC_HEADERS = {
    "User-Agent": "smartmoney/1.0 danut.fagadau@gmail.com",
}


def _get_cik_map() -> dict[str, str]:
    """
    Fetch maparea globală ticker → CIK din SEC.
    Cache în proces — se reîncarcă pe fiecare restart, nu e big deal.
    """
    global _cik_map
    if _cik_map is not None:
        return _cik_map

    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        resp = requests.get(url, headers=SEC_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        _cik_map = {}
        for entry in data.values():
            ticker = entry.get("ticker", "").upper()
            cik = entry.get("cik_str", "")
            if ticker and cik:
                _cik_map[ticker] = str(cik).zfill(10)

        return _cik_map
    except Exception as e:
        log_warn(f"[SIC] CIK map download failed: {e}")
        _cik_map = {}
        return {}


def get_sic_code(ticker: str) -> dict:
    """
    Descarcă SIC code + description pentru un ticker.

    Return: {
        "sic_code":        int | None,
        "sic_description": str | None,
    }
    """
    ticker = (ticker or "").upper()
    if not ticker:
        return {"sic_code": None, "sic_description": None}

    # Verifică cache
    if ticker in _sic_cache:
        cached = _sic_cache[ticker]
        if cached is None:
            return {"sic_code": None, "sic_description": None}
        code, desc = cached
        return {"sic_code": code, "sic_description": desc}

    # Fetch CIK
    cik_map = _get_cik_map()
    cik = cik_map.get(ticker)
    if not cik:
        _sic_cache[ticker] = None
        return {"sic_code": None, "sic_description": None}

    try:
        # Fetch submissions JSON din SEC — conține SIC code
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = requests.get(url, headers=SEC_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # SIC se află la nivelul top al JSON-ului, nu în entityInformation
        sic_code = str(data.get("sic", "") or "").strip()
        sic_desc = str(data.get("sicDescription", "") or "").strip()

        if sic_code and sic_code.isdigit():
            sic_code = int(sic_code)
            _sic_cache[ticker] = (sic_code, sic_desc or None)
            return {"sic_code": sic_code, "sic_description": sic_desc or None}
        else:
            _sic_cache[ticker] = None
            return {"sic_code": None, "sic_description": None}

    except Exception as e:
        log_warn(f"[SIC] {ticker} fetch failed: {e}")
        _sic_cache[ticker] = None
        return {"sic_code": None, "sic_description": None}
    finally:
        # Rate limiting — respectuos cu SEC
        time.sleep(0.2)
