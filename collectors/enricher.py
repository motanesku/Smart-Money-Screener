"""
Enrich — colecteaza semnale smart money pentru candidatii din scan.
Ruleaza de 2x/zi: 08:45 ET si 16:30 ET.
Compatibil cu surse gratuite si consum moderat de API.
"""
import os
import re
import sys
import time
from datetime import date, timedelta

import requests
import yfinance as yf

FMP_KEY = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"
SEC_HEADERS = {"User-Agent": "SmartMoneyScreener/1.0 admin@example.com"}
FINRA_BASE = "https://api.finra.org/data/group/otcMarket/name/regShoDaily"
COMPANY_TICKERS_CACHE = None


def fmp_get(endpoint: str, params: dict | None = None) -> list | dict:
    params = params or {}
    try:
        payload = {**params, "apikey": FMP_KEY}
        r = requests.get(f"{FMP_BASE}/{endpoint}", params=payload, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  FMP {endpoint} error: {e}")
        return {}


def get_profile(ticker: str) -> dict:
    data = fmp_get("profile", {"symbol": ticker})
    if isinstance(data, list) and data:
        p = data[0]
    elif isinstance(data, dict):
        p = data
    else:
        return {}

    return {
        "sector": p.get("sector") or "",
        "industry": p.get("industry") or "",
        "pe_ratio": p.get("pe") or p.get("peRatio"),
        "market_cap": int(p.get("mktCap") or p.get("marketCap") or 0),
        "inst_ownership_pct": p.get("institutionalOwnershipPercentage"),
    }


def classify_role(raw_role: str | None) -> tuple[str, int]:
    role = (raw_role or "").strip().upper()
    if not role:
        return "Unknown", 0
    if "CEO" in role or "CHIEF EXECUTIVE" in role or role == "PRESIDENT":
        return "CEO", 20
    if "CFO" in role or "CHIEF FINANCIAL" in role:
        return "CFO", 18
    if "COO" in role or "CHIEF OPERATING" in role:
        return "COO", 16
    if "CHIEF" in role or "OFFICER" in role:
        return "Officer", 14
    if "10%" in role or "10 PERCENT" in role or "BENEFICIAL OWNER" in role:
        return "10% Owner", 12
    if "DIRECTOR" in role or role == "DIR":
        return "Director", 8
    return raw_role.title(), 4


def get_insider_trades_fmp(ticker: str, days_back: int = 90) -> dict:
    since = (date.today() - timedelta(days=days_back)).isoformat()
    data = fmp_get("insider-trading/latest", {"symbol": ticker, "limit": 100})

    default = {
        "insider_buys_90d": 0,
        "insider_buy_value": 0.0,
        "insider_sells_90d": 0,
        "insider_quality_score": 0,
        "top_insider_role": "Unknown",
    }
    if not isinstance(data, list):
        return default

    buys = 0
    buy_value = 0.0
    sells = 0
    quality_score = 0
    best_role_points = -1
    best_role = "Unknown"

    for trade in data:
        trade_date = trade.get("transactionDate") or trade.get("filingDate") or ""
        if trade_date and trade_date < since:
            continue

        tx_type = (trade.get("transactionType") or trade.get("acquistionOrDisposition") or "").upper()
        shares = abs(float(trade.get("securitiesTransacted") or trade.get("shares") or 0))
        price = float(trade.get("price") or trade.get("transactionPrice") or 0)
        value = shares * price

        role_text = (
            trade.get("typeOfOwner")
            or trade.get("ownerType")
            or trade.get("officerTitle")
            or trade.get("title")
            or trade.get("reportingOwnerRelationship")
            or ""
        )
        role_name, role_points = classify_role(role_text)

        if tx_type in ("P", "A", "PURCHASE", "P-PURCHASE", "BUY"):
            buys += 1
            buy_value += value
            quality_score += role_points
            if role_points > best_role_points:
                best_role_points = role_points
                best_role = role_name
        elif tx_type in ("S", "D", "SALE", "S-SALE", "SELL"):
            sells += 1
            if role_points > best_role_points:
                best_role_points = role_points
                best_role = role_name

    return {
        "insider_buys_90d": buys,
        "insider_buy_value": round(buy_value, 2),
        "insider_sells_90d": sells,
        "insider_quality_score": min(20, quality_score),
        "top_insider_role": best_role,
    }


def get_short_interest(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        si = info.get("shortPercentOfFloat") or 0
        return {"short_interest_pct": round(si * 100, 2) if si and si < 1 else round(si, 2)}
    except Exception:
        return {"short_interest_pct": None}


def load_company_tickers() -> dict:
    global COMPANY_TICKERS_CACHE
    if COMPANY_TICKERS_CACHE is not None:
        return COMPANY_TICKERS_CACHE
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        COMPANY_TICKERS_CACHE = {
            item.get("ticker", "").upper(): str(item.get("cik_str", "")).zfill(10)
            for item in data.values()
            if item.get("ticker")
        }
    except Exception as e:
        print(f"  SEC company_tickers error: {e}")
        COMPANY_TICKERS_CACHE = {}
    return COMPANY_TICKERS_CACHE


def extract_pct_from_text(text: str) -> float | None:
    patterns = [
        r"percent of class represented by amount in row \\(11\\)[^\d]{0,80}(\d+(?:\.\d+)?)\s*%",
        r"percent of class represented by amount in row 11[^\d]{0,80}(\d+(?:\.\d+)?)\s*%",
        r"aggregate amount beneficially owned.*?percent[^\d]{0,80}(\d+(?:\.\d+)?)\s*%",
    ]
    lower = text.lower()
    for pat in patterns:
        m = re.search(pat, lower, flags=re.DOTALL)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    generic = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
    candidates = []
    for item in generic:
        try:
            val = float(item)
            if 4.5 <= val <= 100:
                candidates.append(val)
        except Exception:
            pass
    return max(candidates) if candidates else None


def extract_holder_from_text(text: str) -> str:
    patterns = [
        r"name of reporting person[^A-Za-z]{0,40}([A-Z][A-Z0-9 .,\-&]{3,120})",
        r"reporting person[^A-Za-z]{0,40}([A-Z][A-Z0-9 .,\-&]{3,120})",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            holder = re.sub(r"\s+", " ", m.group(1)).strip(" .:-")
            if 3 <= len(holder) <= 120:
                return holder.title()
    return ""


def score_ownership_form(form: str, pct: float | None, age_days: int) -> tuple[int, str]:
    score = 0
    if form == "SC 13D":
        score = 25
    elif form == "SC 13D/A":
        score = 15
    elif form == "SC 13G":
        score = 8
    elif form == "SC 13G/A":
        score = 5

    if pct and pct >= 10:
        score += 5
    if age_days > 180:
        score = max(0, score - 5)

    label = form if form else "No recent 13D/13G"
    return min(30, score), label


def get_ownership_signal_sec(ticker: str, lookback_days: int = 365) -> dict:
    result = {
        "ownership_form": "",
        "ownership_holder": "",
        "ownership_pct": None,
        "ownership_signal": "No recent 13D/13G filing",
        "score_ownership": 0,
    }
    cik = load_company_tickers().get(ticker.upper())
    if not cik:
        return result
    try:
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=SEC_HEADERS, timeout=20)
        r.raise_for_status()
        sub = r.json()
        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])

        cutoff = date.today() - timedelta(days=lookback_days)
        selected = None
        for form, filing_date, accession, primary_doc in zip(forms, dates, accessions, docs):
            if form not in {"SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"}:
                continue
            try:
                fd = date.fromisoformat(filing_date)
            except Exception:
                continue
            if fd < cutoff:
                continue
            selected = (form, filing_date, accession, primary_doc)
            break

        if not selected:
            return result

        form, filing_date, accession, primary_doc = selected
        age_days = (date.today() - date.fromisoformat(filing_date)).days
        pct = None
        holder = ""
        if accession and primary_doc:
            acc_no_dash = accession.replace("-", "")
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/{primary_doc}"
            try:
                time.sleep(0.15)
                doc = requests.get(filing_url, headers=SEC_HEADERS, timeout=20)
                doc.raise_for_status()
                text = doc.text
                pct = extract_pct_from_text(text)
                holder = extract_holder_from_text(text)
            except Exception as e:
                print(f"  {ticker} 13D/13G parse error: {e}")

        score, label = score_ownership_form(form, pct, age_days)
        result.update({
            "ownership_form": form,
            "ownership_holder": holder,
            "ownership_pct": pct,
            "ownership_signal": f"{label} filed {filing_date}" if not holder else f"{label} by {holder} filed {filing_date}",
            "score_ownership": score,
        })
        return result
    except Exception as e:
        print(f"  {ticker} ownership SEC error: {e}")
        return result


def get_daily_short_sale_volume(ticker: str) -> dict:
    result = {
        "short_sale_volume": None,
        "total_volume_reported": None,
        "short_sale_ratio": None,
        "score_short_flow": 0,
        "short_flow_signal": "Daily short sale volume unavailable",
    }
    payload = {
        "limit": 40,
        "fields": [
            "tradeReportDate",
            "securitiesInformationProcessorSymbolIdentifier",
            "shortParQuantity",
            "shortExemptParQuantity",
            "totalParQuantity",
        ],
        "compareFilters": [
            {
                "compareType": "equal",
                "fieldName": "securitiesInformationProcessorSymbolIdentifier",
                "fieldValue": ticker.upper(),
            }
        ],
    }
    try:
        r = requests.post(
            FINRA_BASE,
            json=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SmartMoneyScreener/1.0"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or not data:
            return result

        grouped = {}
        for row in data:
            d = row.get("tradeReportDate")
            if not d:
                continue
            g = grouped.setdefault(d, {"short": 0, "total": 0})
            g["short"] += int(row.get("shortParQuantity") or 0) + int(row.get("shortExemptParQuantity") or 0)
            g["total"] += int(row.get("totalParQuantity") or 0)

        if not grouped:
            return result
        latest_date = max(grouped.keys())
        short_vol = grouped[latest_date]["short"]
        total_vol = grouped[latest_date]["total"]
        ratio = round((short_vol / total_vol) * 100, 2) if total_vol else None

        score = 0
        signal = "Balanced short flow"
        if ratio is not None:
            if ratio >= 70:
                score = -10
                signal = "Very heavy daily short pressure (>70%)"
            elif ratio >= 60:
                score = -5
                signal = "Heavy daily short pressure (>60%)"
            elif ratio <= 35:
                score = 5
                signal = "Light short pressure (<35%)"

        result.update({
            "short_sale_volume": short_vol,
            "total_volume_reported": total_vol,
            "short_sale_ratio": ratio,
            "score_short_flow": score,
            "short_flow_signal": f"{signal} on {latest_date}",
        })
        return result
    except Exception as e:
        print(f"  {ticker} FINRA short sale error: {e}")
        return result


def score_volume(vol_ratio: float | int | None) -> tuple[int, str]:
    v = float(vol_ratio or 0)
    if v >= 5:
        return 25, "Extreme volume spike (>5x)"
    if v >= 3:
        return 15, "Strong unusual volume (>3x)"
    if v >= 2:
        return 8, "Unusual volume (>2x)"
    return 0, "Normal volume"


def score_insider(buys: int, buy_value: float, sells: int) -> tuple[int, int, str]:
    score = 0
    penalty = 0
    if buy_value >= 1_000_000:
        score += 35
    elif buy_value >= 250_000:
        score += 20
    elif buys >= 3:
        score += 20
    elif buys >= 1:
        score += 10

    if sells >= 10:
        penalty -= 12
    elif sells >= 5:
        penalty -= 6
    elif sells >= 1:
        penalty -= 2

    if buy_value >= 1_000_000:
        signal = "Strong insider conviction"
    elif buys >= 1:
        signal = "Some insider buying detected"
    elif sells >= 5:
        signal = "Heavy insider selling"
    elif sells >= 1:
        signal = "Some insider selling"
    else:
        signal = "No meaningful insider activity"
    return score, penalty, signal


def score_short_interest(si: float | None) -> tuple[int, str]:
    if si is None:
        return 0, "Short interest unavailable"
    s = float(si)
    if 0 < s <= 5:
        return 10, "Low short interest (<5%)"
    if s <= 15:
        return 5, "Moderate short interest (5-15%)"
    if s <= 25:
        return 0, "High short interest (watch risk)"
    return -10, "Very high short interest (>25%)"


def score_fundamental(pe_ratio: float | None, inst_ownership_pct: float | None) -> tuple[int, str]:
    score = 0
    notes = []
    pe = float(pe_ratio or 0)
    inst = float(inst_ownership_pct or 0)
    if 5 <= pe <= 25:
        score += 10
        notes.append("P/E in reasonable range")
    elif 25 < pe <= 40:
        score += 5
        notes.append("P/E acceptable but not cheap")
    elif pe > 40:
        notes.append("P/E elevated")
    if inst >= 60:
        score += 10
        notes.append("Strong institutional ownership")
    elif inst >= 40:
        score += 5
        notes.append("Decent institutional ownership")
    return score, "; ".join(notes) if notes else "Limited fundamental support"


def build_thesis(data: dict) -> str:
    parts = []
    if (data.get("score_volume") or 0) >= 15:
        parts.append("volume unusual")
    if (data.get("score_insider") or 0) >= 20:
        parts.append("insider buying meaningful")
    if (data.get("score_insider_quality") or 0) >= 14:
        parts.append("high-quality insider involved")
    if (data.get("score_ownership") or 0) >= 15:
        parts.append("recent 13D/13G ownership signal")
    if (data.get("score_short_interest") or 0) > 0:
        parts.append("short interest manageable")
    if (data.get("score_short_flow") or 0) < 0:
        parts.append("daily short flow still heavy")
    if (data.get("score_fundamental") or 0) >= 10:
        parts.append("fundamentals acceptable")
    if (data.get("score_penalty") or 0) < 0:
        parts.append("but insider selling tempers conviction")
    if not parts:
        return "Weak setup. Mostly watchlist candidate, not high-conviction."
    return ", ".join(parts).capitalize() + "."


def calculate_scores(data: dict) -> dict:
    vol_score, vol_signal = score_volume(data.get("vol_ratio"))
    insider_score, penalty, insider_signal = score_insider(
        int(data.get("insider_buys_90d") or 0),
        float(data.get("insider_buy_value") or 0),
        int(data.get("insider_sells_90d") or 0),
    )
    short_score, short_signal = score_short_interest(data.get("short_interest_pct"))
    fundamental_score, _ = score_fundamental(data.get("pe_ratio"), data.get("inst_ownership_pct"))

    total = (
        vol_score
        + insider_score
        + int(data.get("insider_quality_score") or 0)
        + int(data.get("score_ownership") or 0)
        + short_score
        + int(data.get("score_short_flow") or 0)
        + fundamental_score
        + penalty
    )
    total = max(0, min(100, total))

    data["score_volume"] = vol_score
    data["score_insider"] = insider_score
    data["score_short_interest"] = short_score
    data["score_fundamental"] = fundamental_score
    data["score_penalty"] = penalty
    data["score"] = total
    data["volume_signal"] = vol_signal
    data["insider_signal"] = insider_signal
    data["short_signal"] = short_signal
    data["thesis"] = build_thesis(data)
    return data


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    enriched = []
    total = len(candidates)
    print(f"Enrich pentru {total} candidati...")
    print(f"FMP calls estimate: ~{total * 2} din 250 disponibile")

    for i, candidate in enumerate(candidates):
        ticker = candidate["ticker"]
        data = {**candidate}
        print(f"  [{i+1}/{total}] {ticker}")

        profile = get_profile(ticker)
        data.update(profile)
        time.sleep(0.20)

        insider = get_insider_trades_fmp(ticker)
        data.update(insider)
        time.sleep(0.20)

        data.update(get_short_interest(ticker))
        time.sleep(0.10)

        data.update(get_ownership_signal_sec(ticker))
        time.sleep(0.20)

        data.update(get_daily_short_sale_volume(ticker))
        time.sleep(0.20)

        data = calculate_scores(data)
        enriched.append(data)

    enriched.sort(key=lambda x: x["score"], reverse=True)
    if enriched:
        top = enriched[0]
        print(f"\nTop scorer: {top['ticker']} = {top['score']}/100")
    return enriched


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched

    candidates = get_scan_results(days_back=1)
    if not candidates:
        print("Niciun candidat azi")
        sys.exit(0)

    enriched = enrich_candidates(candidates)
    if enriched:
        save_enriched(enriched)
        print(f"\nSalvat {len(enriched)} tickers in Supabase")
        for e in enriched[:10]:
            print(
                f"  {e['ticker']:<8} score={e['score']}/100 "
                f"vol={e.get('score_volume',0)} insider={e.get('score_insider',0)} "
                f"iq={e.get('insider_quality_score',0)} own={e.get('score_ownership',0)} "
                f"short={e.get('score_short_interest',0)} flow={e.get('score_short_flow',0)} pen={e.get('score_penalty',0)}"
            )
