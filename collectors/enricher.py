"""
Enricher v9 — modificări față de v8.1:
- Scor NOU: Volume 40 + Short Flow 25 + Short Interest 20 + Ownership 15
- Insider buy/sell: info vizibil, NU influențează scorul
- Insider sell: neutru, nu penalizat
- Istoric 30 zile (limit ridicat în db.py)
"""
import os, sys, time
from datetime import date, timedelta
import requests
import yfinance as yf
from collectors.edgar import get_insider_transactions_detailed

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"


def fmp_get(endpoint: str, params: dict | None = None) -> list | dict:
    try:
        p = {**(params or {}), "apikey": FMP_KEY}
        r = requests.get(f"{FMP_BASE}/{endpoint}", params=p, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  FMP /{endpoint} error: {e}")
        return {}


def get_profile(ticker: str) -> dict:
    data = fmp_get("profile", {"symbol": ticker})
    if isinstance(data, list) and data:   p = data[0]
    elif isinstance(data, dict) and data: p = data
    else: return {}
    return {
        "company_name":       p.get("companyName") or p.get("name") or "",
        "sector":             p.get("sector") or "",
        "industry":           p.get("industry") or "",
        "pe_ratio":           p.get("pe") or p.get("peRatio"),
        "market_cap":         int(p.get("mktCap") or p.get("marketCap") or 0),
        "inst_ownership_pct": p.get("institutionalOwnershipPercentage"),
        "beta":               p.get("beta"),
    }


ROLE_SCORE = {
    "ceo": ("CEO", 20), "chief executive": ("CEO", 20),
    "cfo": ("CFO", 18), "chief financial": ("CFO", 18),
    "coo": ("COO", 16), "chief operating": ("COO", 16),
    "president": ("President", 15),
    "10%": ("10% Owner", 10), "10 percent": ("10% Owner", 10),
    "director": ("Director", 8),
    "officer": ("Officer", 6),
    "vp": ("VP", 5), "vice president": ("VP", 5),
}

def normalize_role(raw: str) -> tuple[str, int]:
    r = (raw or "").lower().strip()
    if not r: return "Unknown", 0
    for key, (name, score) in ROLE_SCORE.items():
        if key in r: return name, score
    return raw.title()[:30], 3


def get_insider_trades_fmp(ticker: str, days_back: int = 90) -> dict:
    """
    FMP /stable/insider-trading?symbol=X
    Insider = INFO ONLY, nu influențează scorul.
    Sell = neutru (poate fi semnal de exit pentru trader).
    """
    since   = (date.today() - timedelta(days=days_back)).isoformat()
    default = {"insider_buys_90d": 0, "insider_buy_value": 0.0,
               "insider_sells_90d": 0, "insider_sell_value": 0.0,
               "top_insider_role": "Unknown", "insider_quality_score": 0}

    data = fmp_get("insider-trading", {"symbol": ticker.upper(), "limit": 100})
    if not isinstance(data, list):
        data = fmp_get("insider-trading/search", {"symbol": ticker.upper(), "limit": 100})
    if not isinstance(data, list) or not data:
        return default

    buys = sells = 0
    buy_value = sell_value = 0.0
    best_role, best_score = "Unknown", 0

    for trade in data:
        td = trade.get("transactionDate") or trade.get("filingDate") or ""
        if td and td < since:
            continue

        disp = (trade.get("acquistionOrDisposition") or
                trade.get("acquisitionOrDisposition") or "").upper().strip()
        tx   = (trade.get("transactionType") or "").upper().strip()

        shares = abs(float(trade.get("securitiesTransacted") or 0) or 0)
        price  = float(trade.get("price") or 0)
        value  = shares * price

        raw_role = (trade.get("typeOfOwner") or
                    trade.get("reportingOwnerRelationship") or
                    trade.get("officerTitle") or "")
        rname, rscore = normalize_role(raw_role)
        if rscore > best_score:
            best_score = rscore
            best_role  = rname

        is_buy  = disp == "A" or tx in ("P-PURCHASE", "P", "BUY", "PURCHASE")
        is_sell = disp == "D" or tx in ("S-SALE", "S", "SELL", "SALE")

        if is_buy:
            buys += 1; buy_value += value
        elif is_sell:
            sells += 1; sell_value += value

    return {
        "insider_buys_90d":     buys,
        "insider_buy_value":    round(buy_value, 2),
        "insider_sells_90d":    sells,
        "insider_sell_value":   round(sell_value, 2),
        "top_insider_role":     best_role,
        "insider_quality_score": best_score,
    }


def get_short_data(ticker: str) -> dict:
    result = {"short_interest_pct": None, "short_sale_ratio": None,
              "short_sale_volume": 0, "total_volume_reported": 0,
              "short_flow_signal": ""}
    try:
        info = yf.Ticker(ticker).info
        si   = float(info.get("shortPercentOfFloat") or 0)
        if si and si < 1: si = si * 100
        result["short_interest_pct"] = round(si, 2) if si else None
    except Exception:
        pass
    try:
        today_str = date.today().strftime("%Y%m%d")
        url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{today_str}.txt"
        r   = requests.get(url, timeout=10)
        if r.status_code == 200:
            for line in r.text.splitlines():
                parts = line.split("|")
                if len(parts) >= 4 and parts[0].upper() == ticker.upper():
                    sv = int(parts[1]) if parts[1].isdigit() else 0
                    tv = int(parts[3]) if parts[3].isdigit() else 0
                    if tv > 0:
                        ratio = round(sv / tv, 4)
                        result["short_sale_volume"]     = sv
                        result["total_volume_reported"] = tv
                        result["short_sale_ratio"]      = ratio
                        if ratio >= 0.60:   result["short_flow_signal"] = f"High short flow ({ratio*100:.0f}%)"
                        elif ratio >= 0.45: result["short_flow_signal"] = f"Elevated short flow ({ratio*100:.0f}%)"
                        else:               result["short_flow_signal"] = f"Normal short flow ({ratio*100:.0f}%)"
                    break
    except Exception:
        pass
    return result


def get_ownership_data(ticker: str) -> dict:
    result = {"ownership_form": "", "ownership_holder": "",
              "ownership_pct": None, "ownership_signal": "", "score_ownership": 0}
    data = fmp_get("acquisition-of-beneficial-ownership", {"symbol": ticker})
    if not isinstance(data, list) or not data:
        return result
    latest = data[0]
    form   = latest.get("form") or latest.get("formType") or ""
    holder = latest.get("reportingName") or latest.get("filerName") or ""
    pct    = latest.get("ownershipPercentage") or latest.get("percentOwned")
    result.update({"ownership_form": form, "ownership_holder": holder,
                   "ownership_pct": float(pct) if pct else None})
    if "13D" in form.upper():
        result["ownership_signal"] = "Active 13D filing (activist)"
        result["score_ownership"]  = 15
    elif "13G" in form.upper():
        result["ownership_signal"] = "Passive 13G filing"
        result["score_ownership"]  = 8
    elif form:
        result["ownership_signal"] = f"Recent {form} filing"
        result["score_ownership"]  = 4
    return result


def get_price_volume(ticker: str) -> dict:
    """
    Prețuri și volume pentru tickerii din watchlist care nu au date din scan.
    """
    try:
        hist = yf.download(ticker, period="25d", interval="1d",
                           auto_adjust=True, progress=False)
        if hist is None or len(hist) < 5:
            return {}
        hist = hist.dropna(subset=["Close", "Volume"])
        price      = float(hist["Close"].iloc[-1])
        vol_today  = float(hist["Volume"].iloc[-1])
        avg_vol    = float(hist["Volume"].iloc[:-1].tail(20).mean())
        vol_ratio  = round(vol_today / avg_vol, 2) if avg_vol > 0 else 0
        return {
            "price":         round(price, 2),
            "volume":        int(vol_today),
            "avg_volume_20d": int(avg_vol),
            "vol_ratio":     vol_ratio,
        }
    except Exception:
        return {}


def build_signals_and_scores(data: dict) -> dict:
    """
    SCOR NOU v9:
    - Volume:        max 40 pts  (principalul indicator)
    - Short Flow:    max 25 pts  (presiune reală pe acțiune)
    - Short Interest: max 20 pts (context short squeeze / distribuție)
    - Ownership 13D/13G: max 15 pts (intrare instituțională semnificativă)
    - Insider: INFO ONLY, nu în scor
    Total: 100 pts
    """
    # ── Volume (40 pts) ───────────────────────────────────────────────────────
    vol = float(data.get("vol_ratio") or 0)
    if vol >= 10:  sv = 40; vsig = "Extreme volume spike (>10x)"
    elif vol >= 5: sv = 32; vsig = "Very high volume spike (>5x)"
    elif vol >= 3: sv = 22; vsig = "Strong unusual volume (>3x)"
    elif vol >= 2: sv = 12; vsig = "Moderate unusual volume (>2x)"
    elif vol >= 1.5: sv = 5; vsig = "Slight volume increase (>1.5x)"
    else:           sv = 0;  vsig = "Normal volume"

    # ── Short Flow (25 pts) ───────────────────────────────────────────────────
    sr = data.get("short_sale_ratio")
    sr = float(sr) if sr is not None else None
    if sr is None:     sf = 0;  sfsig = "Short flow data unavailable"
    elif sr >= 0.70:   sf = 25; sfsig = f"Very high short flow ({sr*100:.0f}%) — strong pressure"
    elif sr >= 0.60:   sf = 18; sfsig = f"High short flow ({sr*100:.0f}%) — elevated pressure"
    elif sr >= 0.50:   sf = 10; sfsig = f"Elevated short flow ({sr*100:.0f}%)"
    elif sr >= 0.40:   sf = 5;  sfsig = f"Moderate short flow ({sr*100:.0f}%)"
    else:              sf = 0;  sfsig = f"Normal short flow ({sr*100:.0f}%)" if sr else "Short flow data unavailable"

    # ── Short Interest (20 pts) ───────────────────────────────────────────────
    si = data.get("short_interest_pct")
    si = float(si) if si is not None else None
    if si is None:     ss = 0;  shsig = "Short interest unavailable"
    elif si > 30:      ss = 20; shsig = f"Very high short interest ({si:.1f}%) — squeeze potential"
    elif si > 20:      ss = 15; shsig = f"High short interest ({si:.1f}%)"
    elif si > 10:      ss = 8;  shsig = f"Elevated short interest ({si:.1f}%)"
    elif si > 5:       ss = 3;  shsig = f"Moderate short interest ({si:.1f}%)"
    else:              ss = 0;  shsig = f"Low short interest ({si:.1f}%)"

    # ── Ownership 13D/13G (15 pts) ────────────────────────────────────────────
    so = int(data.get("score_ownership") or 0)  # deja calculat în get_ownership_data

    # ── Total ─────────────────────────────────────────────────────────────────
    total = max(0, min(100, sv + sf + ss + so))

    # ── Thesis text ───────────────────────────────────────────────────────────
    parts = []
    if sv > 0:     parts.append(vsig.lower())
    if sf > 0:     parts.append(sfsig.lower())
    if ss > 0:     parts.append(shsig.lower())
    if so > 0:     parts.append(data.get("ownership_signal", "").lower())
    # Insider ca context, nu ca scor
    buys  = int(data.get("insider_buys_90d") or 0)
    sells = int(data.get("insider_sells_90d") or 0)
    if buys > 0:   parts.append(f"{buys} insider buy(s) in 90d — context info")
    if sells > 0:  parts.append(f"{sells} insider sell(s) in 90d — monitor for exit signal")
    if not parts:  parts.append("no significant signals detected")

    return {
        "score":                total,
        "score_volume":         sv,
        "score_insider":        0,       # insider nu mai contribuie la scor
        "score_insider_quality": 0,
        "score_ownership":      so,
        "score_short_interest": ss,
        "score_short_flow":     sf,
        "score_fundamental":    0,
        "score_penalty":        0,
        "volume_signal":        vsig,
        "insider_signal":       f"{buys} buys / {sells} sells (90d, info only)",
        "short_signal":         shsig,
        "short_flow_signal_text": sfsig,
        "thesis":               ". ".join(p.capitalize() for p in parts) + ".",
    }


def enrich_single(ticker: str, scan_data: dict | None = None) -> dict | None:
    """
    Enrich complet pentru un singur ticker.
    scan_data: date din scan (price, volume, vol_ratio) — opțional.
    Dacă lipsesc, le trage direct din yfinance.
    """
    ticker = ticker.upper().strip()
    if not ticker:
        return None

    data = {
        "ticker":               ticker,
        "price":                None,
        "volume":               0,
        "avg_volume_20d":       0,
        "vol_ratio":            0,
        "company_name":         "",
        "sector":               "",
        "industry":             "",
        "pe_ratio":             None,
        "market_cap":           0,
        "inst_ownership_pct":   None,
        "beta":                 None,
        "insider_buys_90d":     0,
        "insider_buy_value":    0.0,
        "insider_sells_90d":    0,
        "insider_sell_value":   0.0,
        "top_insider_role":     "Unknown",
        "insider_quality_score": 0,
        "short_interest_pct":   None,
        "short_sale_ratio":     None,
        "short_sale_volume":    0,
        "total_volume_reported": 0,
        "short_flow_signal":    "",
        "ownership_form":       "",
        "ownership_holder":     "",
        "ownership_pct":        None,
        "ownership_signal":     "",
        "score_ownership":      0,
    }

    # Date din scan dacă există, altfel yfinance
    if scan_data:
        data.update({k: scan_data.get(k) for k in
                     ["price","volume","avg_volume_20d","vol_ratio"] if scan_data.get(k)})
    else:
        pv = get_price_volume(ticker)
        data.update(pv)

    # FMP profile
    data.update(get_profile(ticker))
    time.sleep(0.3)

    # FMP insider (info only)
    insider = get_insider_trades_fmp(ticker)
    if insider.get("insider_buys_90d", 0) == 0 and insider.get("insider_sells_90d", 0) == 0:
        try:
            edgar = get_insider_transactions_detailed(ticker)
            if edgar.get("insider_buys_90d", 0) > 0:
                insider.update(edgar)
        except Exception:
            pass
    data.update(insider)
    time.sleep(0.3)

    # FMP ownership 13D/13G
    data.update(get_ownership_data(ticker))
    time.sleep(0.3)

    # Short data
    data.update(get_short_data(ticker))

    # Score + signals
    data.update(build_signals_and_scores(data))

    return data


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    """Enrich pentru lista de candidați din scan."""
    if not candidates:
        return []

    enriched = []
    total    = len(candidates)
    print(f"Enrich scan candidates: {total} tickers")

    for i, candidate in enumerate(candidates):
        ticker = (candidate.get("ticker") or "").upper().strip()
        print(f"  [{i+1}/{total}] {ticker}")
        result = enrich_single(ticker, scan_data=candidate)
        if result:
            enriched.append(result)

    enriched.sort(key=lambda x: x.get("score", 0), reverse=True)
    if enriched:
        top = enriched[0]
        print(f"\nTop: {top['ticker']} = {top['score']}/100 | {top.get('company_name','')}")
    return enriched


def enrich_watchlist(watchlist_tickers: list[str],
                     scan_results: list[dict]) -> list[dict]:
    """
    Enrich pentru watchlist — independent de scan.
    Dacă ticker-ul e și în scan, folosește datele de acolo.
    Dacă nu, trage price/volume din yfinance.
    """
    if not watchlist_tickers:
        return []

    scan_map = {r.get("ticker","").upper(): r for r in (scan_results or [])}
    enriched = []
    total    = len(watchlist_tickers)
    print(f"Enrich watchlist: {total} tickers")

    for i, ticker in enumerate(watchlist_tickers):
        ticker = ticker.upper().strip()
        print(f"  [{i+1}/{total}] {ticker} {'(din scan)' if ticker in scan_map else '(watchlist only)'}")
        scan_data = scan_map.get(ticker)
        result    = enrich_single(ticker, scan_data=scan_data)
        if result:
            enriched.append(result)

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
        print(f"\nSalvat {len(enriched)} tickers")
        for e in enriched[:10]:
            print(f"  {e['ticker']:<8} score={e['score']:>3}/100  "
                  f"vol={e.get('vol_ratio',0)}x  "
                  f"sf={e.get('short_sale_ratio',0) or 0:.0%}  "
                  f"si={e.get('short_interest_pct',0) or 0:.1f}%  "
                  f"buys={e.get('insider_buys_90d',0)}/sells={e.get('insider_sells_90d',0)}  "
                  f"{e.get('company_name','')[:25]}")
