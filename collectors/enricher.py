"""
Enrich — colecteaza semnale smart money pentru candidatii din scan.
Ruleaza de 2x/zi: 08:45 ET si 16:30 ET.

Scop:
- fara carry-over intre tickere
- insider metrics strict pe tickerul curent
- fallback la zero daca API fail
- fallback EDGAR daca FMP nu da date utile
"""
import os
import sys
import time
from datetime import date, timedelta

import requests
import yfinance as yf

from collectors.edgar import get_insider_transactions_detailed

FMP_KEY = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"


def fmp_get(endpoint: str, params: dict | None = None) -> list | dict:
    try:
        params = params or {}
        p = {**params, "apikey": FMP_KEY}
        r = requests.get(f"{FMP_BASE}/{endpoint}", params=p, timeout=20)
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
        return {
            "sector": "",
            "industry": "",
            "pe_ratio": None,
            "market_cap": 0,
            "inst_ownership_pct": None,
            "beta": None,
        }

    return {
        "sector": p.get("sector") or "",
        "industry": p.get("industry") or "",
        "pe_ratio": p.get("pe") or p.get("peRatio"),
        "market_cap": int(p.get("mktCap") or p.get("marketCap") or 0),
        "inst_ownership_pct": p.get("institutionalOwnershipPercentage"),
        "beta": p.get("beta"),
    }


def normalize_role(raw_role: str) -> tuple[str, int]:
    role = (raw_role or "").strip().upper()

    if not role:
        return "Unknown", 0
    if "CHIEF EXECUTIVE" in role or role == "CEO":
        return "CEO", 20
    if "CHIEF FINANCIAL" in role or role == "CFO":
        return "CFO", 18
    if "10%" in role or "10 PERCENT OWNER" in role or "10% OWNER" in role:
        return "10% Owner", 10
    if "DIRECTOR" in role:
        return "Director", 8
    if "OFFICER" in role:
        return "Officer", 6

    return raw_role.title(), 4


def get_insider_trades_fmp(ticker: str, days_back: int = 90) -> dict:
    """
    FMP insider trades.
    IMPORTANT:
    - filtreaza strict pe simbolul curent
    - initializeaza totul local per ticker
    - daca nu gaseste date bune, returneaza zero + Unknown
    """
    since = (date.today() - timedelta(days=days_back)).isoformat()
    ticker_u = ticker.upper().strip()

    default = {
        "insider_buys_90d": 0,
        "insider_buy_value": 0.0,
        "insider_sells_90d": 0,
        "top_insider_role": "Unknown",
        "insider_quality_score": 0,
    }

    data = fmp_get("insider-trading/latest", {"symbol": ticker_u, "limit": 100})
    if not isinstance(data, list) or not data:
        return default

    buys = 0
    buy_value = 0.0
    sells = 0
    best_role = "Unknown"
    best_role_score = 0

    filtered_count = 0

    for trade in data:
        # Filtru strict pe simbol.
        trade_symbol = (
            trade.get("symbol")
            or trade.get("ticker")
            or trade.get("companySymbol")
            or ""
        ).upper().strip()

        if trade_symbol and trade_symbol != ticker_u:
            continue

        trade_date = trade.get("transactionDate") or trade.get("filingDate") or ""
        if trade_date and trade_date < since:
            continue

        filtered_count += 1

        tx_type = (
            trade.get("transactionType")
            or trade.get("acquistionOrDisposition")
            or trade.get("acquisitionOrDisposition")
            or ""
        ).upper().strip()

        shares = abs(float(trade.get("securitiesTransacted") or trade.get("shares") or 0) or 0)
        price = float(trade.get("price") or trade.get("transactionPrice") or 0 or 0)
        value = shares * price

        raw_role = (
            trade.get("reportingOwnerRelationship")
            or trade.get("reportingOwnerTitle")
            or trade.get("reportingOwnerRole")
            or trade.get("title")
            or trade.get("officerTitle")
            or ""
        )
        role_name, role_score = normalize_role(raw_role)
        if role_score > best_role_score:
            best_role_score = role_score
            best_role = role_name

        if tx_type in ("P", "A", "PURCHASE", "P-PURCHASE", "BUY"):
            buys += 1
            buy_value += value
        elif tx_type in ("S", "D", "SALE", "S-SALE", "SELL"):
            sells += 1

    # Dacă endpointul a răspuns cu date dar niciuna nu era pentru tickerul curent,
    # considerăm răspunsul nefolositor și revenim la default.
    if filtered_count == 0:
        return default

    return {
        "insider_buys_90d": buys,
        "insider_buy_value": round(buy_value, 2),
        "insider_sells_90d": sells,
        "top_insider_role": best_role,
        "insider_quality_score": best_role_score,
    }


def get_short_interest(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        si = info.get("shortPercentOfFloat") or 0
        if si and si < 1:
            si = si * 100
        return {"short_interest_pct": round(float(si), 2)}
    except Exception:
        return {"short_interest_pct": None}


def build_signals_and_scores(data: dict) -> dict:
    score_volume = 0
    score_insider = 0
    score_short_interest = 0
    score_fundamental = 0
    score_penalty = 0

    # Volume
    vol = float(data.get("vol_ratio") or 0)
    if vol >= 5:
        score_volume = 25
        volume_signal = "Extreme volume spike (>5x)"
    elif vol >= 3:
        score_volume = 15
        volume_signal = "Strong unusual volume (>3x)"
    elif vol >= 2:
        score_volume = 8
        volume_signal = "Moderate unusual volume (>2x)"
    else:
        volume_signal = "Normal volume"

    # Insider
    buys = int(data.get("insider_buys_90d") or 0)
    buy_value = float(data.get("insider_buy_value") or 0)
    sells = int(data.get("insider_sells_90d") or 0)
    quality = int(data.get("insider_quality_score") or 0)

    if buy_value >= 1_000_000:
        score_insider = 35
        insider_signal = "Heavy insider buying (>$1M)"
    elif buy_value >= 250_000:
        score_insider = 20
        insider_signal = "Some insider buying detected"
    elif buys >= 3:
        score_insider = 18
        insider_signal = "Cluster insider buying detected"
    elif buys >= 1:
        score_insider = 10
        insider_signal = "Light insider buying detected"
    else:
        insider_signal = "No meaningful insider buying"

    score_insider += quality

    if sells >= 20:
        score_penalty -= 15
    elif sells >= 10:
        score_penalty -= 12
    elif sells >= 5:
        score_penalty -= 6

    # Short interest
    si = data.get("short_interest_pct")
    si = float(si) if si is not None else None
    if si is None:
        short_signal = "Short interest unavailable"
    elif 0 < si < 5:
        score_short_interest = 10
        short_signal = "Low short interest (<5%)"
    elif si <= 15:
        score_short_interest = 5
        short_signal = "Moderate short interest (5-15%)"
    elif si > 30:
        score_short_interest = -10
        short_signal = "Very high short interest (>30%)"
    else:
        short_signal = "Elevated short interest"

    # Fundamentals
    pe = data.get("pe_ratio")
    try:
        pe = float(pe) if pe is not None else None
    except Exception:
        pe = None

    inst = data.get("inst_ownership_pct")
    try:
        inst = float(inst) if inst is not None else None
    except Exception:
        inst = None

    if pe is not None:
        if 5 <= pe <= 25:
            score_fundamental += 10
        elif 25 < pe <= 40:
            score_fundamental += 5

    if inst is not None:
        if inst >= 60:
            score_fundamental += 10
        elif inst >= 40:
            score_fundamental += 5

    total = score_volume + score_insider + score_short_interest + score_fundamental + score_penalty
    total = max(0, min(100, total))

    thesis_parts = []
    if score_volume > 0:
        thesis_parts.append("Volume unusual")
    if score_insider > 0:
        thesis_parts.append("insider buying meaningful")
    if score_short_interest > 0:
        thesis_parts.append("short interest manageable")
    elif score_short_interest < 0:
        thesis_parts.append("short interest elevated")
    if score_penalty < 0:
        thesis_parts.append("insider selling tempers conviction")
    if not thesis_parts:
        thesis_parts.append("signals mixed")

    return {
        "score": total,
        "score_volume": score_volume,
        "score_insider": score_insider,
        "score_short_interest": score_short_interest,
        "score_fundamental": score_fundamental,
        "score_penalty": score_penalty,
        "volume_signal": volume_signal,
        "insider_signal": insider_signal,
        "short_signal": short_signal,
        "thesis": ", ".join(thesis_parts).capitalize() + ".",
    }


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    enriched = []
    total = len(candidates)
    print(f"Enrich pentru {total} candidati...")
    print(f"FMP calls estimate: ~{total * 2} din 250 disponibile")

    for i, candidate in enumerate(candidates):
        ticker = (candidate.get("ticker") or "").upper().strip()
        print(f"  [{i+1}/{total}] {ticker}")

        # IMPORTANT: initializezi tot per ticker, zero carry-over.
        data = {
            **candidate,
            "ticker": ticker,
            "sector": "",
            "industry": "",
            "pe_ratio": None,
            "market_cap": 0,
            "inst_ownership_pct": None,
            "beta": None,
            "insider_buys_90d": 0,
            "insider_buy_value": 0.0,
            "insider_sells_90d": 0,
            "top_insider_role": "Unknown",
            "insider_quality_score": 0,
            "short_interest_pct": None,
        }

        profile = get_profile(ticker)
        data.update(profile)
        time.sleep(0.25)

        insider = get_insider_trades_fmp(ticker)
        # fallback EDGAR doar dacă FMP nu a returnat buys și sells utile
        if (
            insider.get("insider_buys_90d", 0) == 0
            and insider.get("insider_sells_90d", 0) == 0
            and insider.get("insider_buy_value", 0) == 0
        ):
            try:
                edgar = get_insider_transactions_detailed(ticker)
                insider["insider_buys_90d"] = int(edgar.get("insider_buys_90d") or 0)
                insider["insider_buy_value"] = float(edgar.get("insider_buy_value") or 0)
                insider["insider_sells_90d"] = int(edgar.get("insider_sells_90d") or 0)
            except Exception:
                pass

        data.update(insider)
        time.sleep(0.25)

        si = get_short_interest(ticker)
        data.update(si)

        data.update(build_signals_and_scores(data))
        enriched.append(data)

    enriched.sort(key=lambda x: x.get("score", 0), reverse=True)
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
                f"buys={e.get('insider_buys_90d', 0)} "
                f"sells={e.get('insider_sells_90d', 0)} "
                f"role={e.get('top_insider_role', 'Unknown')} "
                f"vol={e.get('vol_ratio', 0)}x"
            )
