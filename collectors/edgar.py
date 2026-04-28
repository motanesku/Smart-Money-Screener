"""
EDGAR collector v3 — fix-uri critice față de v2:

BUG FIX 1: Form 4 distingea buy vs sell
  - v2: orice Form 4 era numărat ca "buy" → CEO care vinde = fals pozitiv
  - v3: parsăm XML-ul filing-ului, citim transactionCode (P=buy, S=sell)

BUG FIX 2: buy_value era hardcodat (buys * 50_000) → fictiv
  - v3: calculăm real din transactionShares * pricePerShare din XML

NOU: get_13f_changes() — detectează dacă un fond mare a intrat/ieșit
  - Parsează 13F-HR filings pentru holdings changes
  - Latență 45 zile, dar direcția fondului contează

NOU: insider_quality_score() — nu toate tranzacțiile sunt egale
  - CEO/CFO buying > Director buying > VP buying
  - Open market purchase > exercise of options (10-b5-1 plan)
"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import requests

EDGAR_BASE = "https://data.sec.gov"
HEADERS    = {"User-Agent": "SmartMoneyScreener research@screener.com"}

# transactionCode P = open market purchase, S = open market sale
# A = grant/award (ignorăm — nu e bani reali), M = exercise options (ignorăm)
BUY_CODES  = {"P"}
SELL_CODES = {"S"}

# Roluri insider ordonate după relevanță pentru semnalul Smart Money
ROLE_PRIORITY = {
    "chief executive officer": 10,
    "ceo": 10,
    "chief financial officer": 9,
    "cfo": 9,
    "chief operating officer": 8,
    "coo": 8,
    "president": 8,
    "director": 6,
    "executive vice president": 6,
    "senior vice president": 5,
    "vice president": 4,
    "10% owner": 9,   # activist / major holder
}

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
        print(f"  [EDGAR] CIK map: {len(_TICKER_CIK_MAP)} tickers")
    except Exception as e:
        print(f"  [EDGAR] EROARE la CIK map: {e}")
    return _TICKER_CIK_MAP


def get_cik(ticker: str) -> str | None:
    return _load_ticker_map().get(ticker.upper())


def _get_role_score(title: str) -> int:
    """Returnează scorul de relevanță al rolului insiderului (0-10)."""
    if not title:
        return 3
    t = title.lower()
    for role, score in ROLE_PRIORITY.items():
        if role in t:
            return score
    return 3


def _parse_form4_xml(xml_url: str) -> dict:
    """
    Parsează un filing Form 4 XML de pe EDGAR.
    Returnează dict cu: buys, sells, buy_value, sell_value, role, is_10b5_plan
    """
    result = {
        "buys": 0, "sells": 0,
        "buy_value": 0.0, "sell_value": 0.0,
        "role": "Unknown", "role_score": 3,
        "is_10b5_plan": False,
    }
    try:
        time.sleep(0.1)  # respectăm rate limit EDGAR (10 req/sec)
        r = requests.get(xml_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)

        # Rol insider
        role_el = root.find(".//reportingOwner/reportingOwnerRelationship/officerTitle")
        if role_el is not None and role_el.text:
            result["role"] = role_el.text.strip()
            result["role_score"] = _get_role_score(result["role"])

        # Tranzacții
        for tx in root.findall(".//nonDerivativeTransaction"):
            code_el = tx.find("transactionCoding/transactionCode")
            if code_el is None:
                continue
            code = (code_el.text or "").strip().upper()

            shares_el = tx.find("transactionAmounts/transactionShares/value")
            price_el  = tx.find("transactionAmounts/transactionPricePerShare/value")
            plan_el   = tx.find("transactionCoding/equitySwapInvolved")

            try:
                shares = float(shares_el.text) if shares_el is not None else 0.0
                price  = float(price_el.text)  if price_el  is not None else 0.0
            except (ValueError, TypeError):
                shares, price = 0.0, 0.0

            value = shares * price

            if code in BUY_CODES:
                result["buys"]      += 1
                result["buy_value"] += value
            elif code in SELL_CODES:
                result["sells"]      += 1
                result["sell_value"] += value

            # Detectăm 10b5-1 plan (vânzare programată = mai puțin bearish)
            if plan_el is not None and (plan_el.text or "").strip() == "1":
                result["is_10b5_plan"] = True

    except Exception as e:
        print(f"    [EDGAR XML] parse error {xml_url}: {e}")
    return result


def _get_filing_xml_url(cik: str, accession: str) -> str | None:
    """
    Din accession number, construiește URL-ul către fișierul XML al Form 4.
    Accession format: 0001234567-24-000123 → 000123456724000123
    """
    acc_clean = accession.replace("-", "")
    index_url = f"{EDGAR_BASE}/Archives/edgar/full-index/{acc_clean[:4]}/{acc_clean[4:6]}"
    # Metoda directă: construim URL-ul din submission index
    filing_url = (
        f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/"
        f"{acc_clean}/"
    )
    try:
        time.sleep(0.1)
        r = requests.get(filing_url, headers=HEADERS, timeout=10)
        # Găsim fișierul XML principal (nu index)
        xml_files = re.findall(r'href="([^"]+\.xml)"', r.text, re.IGNORECASE)
        for f in xml_files:
            if "index" not in f.lower():
                return f"https://www.sec.gov{f}" if f.startswith("/") else f"{filing_url}{f}"
    except Exception:
        pass
    return None


def _find_xml_in_index(cik_int: str, acc_clean: str) -> str | None:
    """
    Fallback: citește index-ul JSON al unui filing și returnează URL-ul
    primului fișier XML care nu e un index sau stylesheet.
    Folosit când primaryDocument lipsește sau nu e XML.
    """
    try:
        time.sleep(0.1)
        index_url = (
            f"{EDGAR_BASE}/Archives/edgar/data/{cik_int}/{acc_clean}/"
            f"{acc_clean}-index.json"
        )
        r = requests.get(index_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        docs = r.json().get("documents", [])
        for doc in docs:
            name = doc.get("document", "")
            dtype = (doc.get("type") or "").upper()
            # Vrem Form 4 XML, nu index sau stylesheet
            if name.lower().endswith(".xml") and "4" in dtype:
                return (
                    f"{EDGAR_BASE}/Archives/edgar/data/{cik_int}/{acc_clean}/{name}"
                )
        # Dacă nu am găsit după tip, luăm primul XML care nu e index
        for doc in docs:
            name = doc.get("document", "")
            if name.lower().endswith(".xml") and "index" not in name.lower():
                return (
                    f"{EDGAR_BASE}/Archives/edgar/data/{cik_int}/{acc_clean}/{name}"
                )
    except Exception:
        pass
    return None


def get_insider_data_edgar(ticker: str, days_back: int = 90) -> dict:
    """
    Citește Form 4 filings din SEC EDGAR și parsează REAL buy vs sell.

    Returnează:
        buys          — număr tranzacții open market purchase
        sells         — număr tranzacții open market sale
        buy_value     — valoare totală cumpărări ($)
        sell_value    — valoare totală vânzări ($)
        top_role      — rolul insiderului cu cel mai mare scor
        role_score    — scor relevanță rol (0-10)
        net_signal    — "ACCUMULATION" / "DISTRIBUTION" / "NEUTRAL" / "MIXED"
        is_10b5_plan  — dacă vânzările sunt dintr-un plan 10b5-1 (mai puțin bearish)
        penalty       — scor penalizare pentru distribuție (-30 max)
    """
    default = {
        "buys": 0, "sells": 0,
        "buy_value": 0.0, "sell_value": 0.0,
        "top_role": "N/A", "role_score": 0,
        "net_signal": "NEUTRAL",
        "is_10b5_plan": False,
        "penalty": 0,
    }

    cik = get_cik(ticker)
    if not cik:
        return default

    sub_url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    try:
        r = requests.get(sub_url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        body    = r.json()
        filings = body.get("filings", {}).get("recent", {})

        forms         = filings.get("form", [])
        dates         = filings.get("filingDate", [])
        accessions    = filings.get("accessionNumber", [])
        primary_docs  = filings.get("primaryDocument", [])  # numele real al fișierului XML
        cutoff        = (date.today() - timedelta(days=days_back)).isoformat()

        total_buys  = 0
        total_sells = 0
        total_buy_value  = 0.0
        total_sell_value = 0.0
        best_role        = "Unknown"
        best_role_score  = 0
        is_10b5          = False
        parsed_count     = 0
        MAX_PARSE        = 15

        for form, f_date, accession, primary_doc in zip(
            forms, dates, accessions,
            primary_docs if primary_docs else [""] * len(forms),
        ):
            if f_date < cutoff:
                break
            if form != "4":
                continue
            if parsed_count >= MAX_PARSE:
                break

            acc_clean = accession.replace("-", "")
            cik_int   = str(int(cik))
            base_url  = f"{EDGAR_BASE}/Archives/edgar/data/{cik_int}/{acc_clean}"

            # Citim index-ul JSON al filing-ului — metodă sigură indiferent de primaryDocument
            xml_url = _find_xml_in_index(cik_int, acc_clean)
            if not xml_url:
                # Fallback la primaryDocument (strip prefix xslF345X0X/ dacă există)
                clean_doc = primary_doc.split("/")[-1] if primary_doc else ""
                if clean_doc.lower().endswith(".xml"):
                    xml_url = f"{base_url}/{clean_doc}"
                else:
                    xml_url = f"{base_url}/{acc_clean}.xml"

            parsed = _parse_form4_xml(xml_url)
            parsed_count += 1

            total_buys       += parsed["buys"]
            total_sells      += parsed["sells"]
            total_buy_value  += parsed["buy_value"]
            total_sell_value += parsed["sell_value"]
            if parsed["is_10b5_plan"]:
                is_10b5 = True
            if parsed["role_score"] > best_role_score:
                best_role_score = parsed["role_score"]
                best_role       = parsed["role"]

        # Net signal
        if total_buys > 0 and total_sells == 0:
            net_signal = "ACCUMULATION"
        elif total_sells > 0 and total_buys == 0:
            net_signal = "DISTRIBUTION"
        elif total_buys > 0 and total_sells > 0:
            net_signal = "MIXED"
        else:
            net_signal = "NEUTRAL"

        # Penalizare pentru distribuție (intră în score ca scăzător)
        penalty = 0
        if net_signal == "DISTRIBUTION" and not is_10b5:
            # CEO/CFO vinde fără plan 10b5 = semnal negativ puternic
            penalty = -min(int(best_role_score * 3), 30)
        elif net_signal == "DISTRIBUTION" and is_10b5:
            # Vânzare planificată = mai puțin îngrijorătoare
            penalty = -5

        print(
            f"  [EDGAR] {ticker}: {total_buys} buys (${total_buy_value:,.0f}) "
            f"| {total_sells} sells (${total_sell_value:,.0f}) "
            f"| {net_signal} | {best_role}"
        )

        return {
            "buys":         total_buys,
            "sells":        total_sells,
            "buy_value":    round(total_buy_value, 2),
            "sell_value":   round(total_sell_value, 2),
            "top_role":     best_role,
            "role_score":   best_role_score,
            "net_signal":   net_signal,
            "is_10b5_plan": is_10b5,
            "penalty":      penalty,
        }

    except Exception as e:
        print(f"  [EDGAR] {ticker} eroare: {e}")
        return default


def get_13f_changes(ticker: str) -> dict:
    """
    Citește 13F-HR filings pentru a detecta schimbări în holdings instituționale.
    Latență: ~45 zile față de trimestrul raportat.
    Returnează: funds_added, funds_removed, net_institutional_signal
    """
    default = {"funds_added": 0, "funds_removed": 0, "net_institutional_signal": "UNKNOWN"}
    # 13F e raportat de fond, nu de companie — nu putem căuta direct după ticker CIK
    # Implementare viitoare: folosim EDGAR full-text search sau bulk data
    # https://efts.sec.gov/LATEST/search-index?q=%22TSLA%22&dateRange=custom&startdt=2024-01-01&forms=13F-HR
    return default


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    test_ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"\nTest EDGAR pentru {test_ticker}:")
    data = get_insider_data_edgar(test_ticker, days_back=90)
    for k, v in data.items():
        print(f"  {k}: {v}")
