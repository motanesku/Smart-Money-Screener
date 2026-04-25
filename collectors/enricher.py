"""
Enricher v10 — FMP folosit DOAR pentru profile (1 call/ticker).
Insider data: SEC EDGAR exclusiv (gratuit, fără limite).
Ownership: SEC EDGAR EDGAR full-text search pentru 13D/13G.
Short data: yfinance + FINRA CSV (gratuit).

FMP calls per run: 1 × nr_candidati (max 26) = 26/250 zilnic.
"""
import os, sys, time
from datetime import date, timedelta
import requests
import yfinance as yf

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"
EDGAR_HEADERS = {"User-Agent": "SmartMoneyScreener contact@screener.com"}


# ── FMP: DOAR profile ─────────────────────────────────────────────────────────

def get_profile(ticker: str) -> dict:
    """FMP /stable/profile — singurul endpoint FMP folosit. 1 call."""
    try:
        r = requests.get(f"{FMP_BASE}/profile",
                         params={"symbol": ticker, "apikey": FMP_KEY}, timeout=20)
        r.raise_for_status()
        data = r.json()
        p = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
        return {
            "company_name":       p.get("companyName") or p.get("name") or "",
            "sector":             p.get("sector") or "",
            "industry":           p.get("industry") or "",
            "pe_ratio":           p.get("pe") or p.get("peRatio"),
            "market_cap":         int(p.get("mktCap") or p.get("marketCap") or 0),
            "inst_ownership_pct": p.get("institutionalOwnershipPercentage"),
            "beta":               p.get("beta"),
        }
    except Exception as e:
        print(f"  FMP profile error {ticker}: {e}")
        return {}


# ── SEC EDGAR: insider Form 4 ─────────────────────────────────────────────────

def get_cik(ticker: str) -> str | None:
    """Caută CIK în company_tickers.json de la SEC."""
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=EDGAR_HEADERS, timeout=15)
        r.raise_for_status()
        for _, c in r.json().items():
            if c.get("ticker", "").upper() == ticker.upper():
                return str(c["cik_str"]).zfill(10)
    except Exception:
        pass
    return None


ROLE_SCORE = {
    "chief executive": ("CEO", 20), "ceo": ("CEO", 20),
    "chief financial": ("CFO", 18), "cfo": ("CFO", 18),
    "chief operating": ("COO", 16), "coo": ("COO", 16),
    "president":       ("President", 15),
    "10%":             ("10% Owner", 10),
    "director":        ("Director", 8),
    "officer":         ("Officer", 6),
    "vp":              ("VP", 5), "vice president": ("VP", 5),
}

def normalize_role(raw: str) -> tuple[str, int]:
    r = (raw or "").lower().strip()
    if not r: return "Unknown", 0
    for key, (name, score) in ROLE_SCORE.items():
        if key in r: return name, score
    return raw.title()[:30], 3


def get_insider_data_edgar(ticker: str, days_back: int = 90) -> dict:
    """
    SEC EDGAR submissions API — Form 4 filings.
    Gratuit, fără API key, fără limite stricte.
    """
    default = {"insider_buys_90d": 0, "insider_buy_value": 0.0,
               "insider_sells_90d": 0, "insider_sell_value": 0.0,
               "top_insider_role": "Unknown", "insider_quality_score": 0}

    cik = get_cik(ticker)
    if not cik:
        return default

    time.sleep(0.1)

    try:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        r   = requests.get(url, headers=EDGAR_HEADERS, timeout=20)
        r.raise_for_status()
        sub      = r.json()
        filings  = sub.get("filings", {}).get("recent", {})
        forms    = filings.get("form", [])
        dates    = filings.get("filingDate", [])
        cutoff   = (date.today() - timedelta(days=days_back)).isoformat()

        buys = sells = 0
        buy_value = sell_value = 0.0
        best_role, best_score = "Unknown", 0

        for form, filing_date in zip(forms, dates):
            if form != "4":
                continue
            if filing_date < cutoff:
                break  # filings sortate descrescător

            # Numărăm Form 4 ca proxy pentru tranzacții
            # Fără parsing XML per filing pentru a nu face prea multe requests
            buys += 1

        # Rol: din ultimul filing Form 4 dacă există
        for form, filing_date in zip(forms, dates):
            if form == "4" and filing_date >= cutoff:
                # Încearcă să extragă rolul din owner info
                officers = sub.get("officers", [])
                if officers:
                    raw = officers[0].get("title") or officers[0].get("name") or ""
                    best_role, best_score = normalize_role(raw)
                break

        return {
            "insider_buys_90d":     buys,
            "insider_buy_value":    buy_value,
            "insider_sells_90d":    sells,
            "insider_sell_value":   sell_value,
            "top_insider_role":     best_role,
            "insider_quality_score": best_score,
        }

    except Exception as e:
        print(f"  EDGAR insider error {ticker}: {e}")
        return default


def get_ownership_edgar(ticker: str) -> dict:
    """
    SEC EDGAR full-text search pentru 13D/13G filings recente.
    Gratuit, fără limite.
    """
    result = {"ownership_form": "", "ownership_holder": "",
              "ownership_pct": None, "ownership_signal": "", "score_ownership": 0}
    try:
        since = (date.today() - timedelta(days=180)).strftime("%Y-%m-%d")
        url   = (f"https://efts.sec.gov/LATEST/search-index"
                 f"?q=%22{ticker}%22&forms=SC+13D,SC+13G,SC+13D/A,SC+13G/A"
                 f"&dateRange=custom&startdt={since}"
                 f"&hits.hits._source=file_date,form_type,display_names&hits.hits.total.value=true")
        r = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
        if not hits:
            return result

        latest   = hits[0].get("_source", {})
        form     = latest.get("form_type") or ""
        holder   = latest.get("display_names") or ""
        if isinstance(holder, list):
            holder = holder[0] if holder else ""

        result["ownership_form"]   = form
        result["ownership_holder"] = str(holder)[:60]

        if "13D" in form.upper():
            result["ownership_signal"] = "Active 13D filing (activist)"
            result["score_ownership"]  = 15
        elif "13G" in form.upper():
            result["ownership_signal"] = "Passive 13G filing"
            result["score_ownership"]  = 8

    except Exception as e:
        print(f"  EDGAR ownership error {ticker}: {e}")

    return result


# ── Short data ────────────────────────────────────────────────────────────────

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
                        if ratio >= 0.70:   result["short_flow_signal"] = f"Very high short flow ({ratio*100:.0f}%)"
                        elif ratio >= 0.60: result["short_flow_signal"] = f"High short flow ({ratio*100:.0f}%)"
                        elif ratio >= 0.50: result["short_flow_signal"] = f"Elevated short flow ({ratio*100:.0f}%)"
                        else:               result["short_flow_signal"] = f"Normal short flow ({ratio*100:.0f}%)"
                    break
    except Exception:
        pass
    return result


def get_price_volume(ticker: str) -> dict:
    try:
        hist = yf.download(ticker, period="25d", interval="1d",
                           auto_adjust=True, progress=False)
        if hist is None or len(hist) < 5:
            return {}
        hist      = hist.dropna(subset=["Close","Volume"])
        price     = float(hist["Close"].iloc[-1])
        vol_today = float(hist["Volume"].iloc[-1])
        avg_vol   = float(hist["Volume"].iloc[:-1].tail(20).mean())
        return {
            "price":          round(price, 2),
            "volume":         int(vol_today),
            "avg_volume_20d": int(avg_vol),
            "vol_ratio":      round(vol_today / avg_vol, 2) if avg_vol > 0 else 0,
        }
    except Exception:
        return {}


# ── Score + signals ───────────────────────────────────────────────────────────

def build_signals_and_scores(data: dict) -> dict:
    """
    Scor v9/v10: Volume(40) + ShortFlow(25) + ShortInterest(20) + Ownership(15)
    Insider = INFO ONLY, nu în scor, sell = neutru
    """
    vol = float(data.get("vol_ratio") or 0)
    if vol >= 10:    sv = 40; vsig = "Spike extrem de volum (>10x)"
    elif vol >= 5:   sv = 32; vsig = "Volum foarte ridicat (>5x)"
    elif vol >= 3:   sv = 22; vsig = "Volum neobișnuit puternic (>3x)"
    elif vol >= 2:   sv = 12; vsig = "Volum neobișnuit moderat (>2x)"
    elif vol >= 1.5: sv = 5;  vsig = "Volum ușor crescut (>1.5x)"
    else:            sv = 0;  vsig = "Volum normal"

    sr = data.get("short_sale_ratio")
    sr = float(sr) if sr is not None else None
    if sr is None:     sf = 0;  sfsig = "Date short flow indisponibile"
    elif sr >= 0.70:   sf = 25; sfsig = f"Short flow foarte ridicat ({sr*100:.0f}%) — presiune puternică"
    elif sr >= 0.60:   sf = 18; sfsig = f"Short flow ridicat ({sr*100:.0f}%) — presiune crescută"
    elif sr >= 0.50:   sf = 10; sfsig = f"Short flow elevat ({sr*100:.0f}%)"
    elif sr >= 0.40:   sf = 5;  sfsig = f"Short flow moderat ({sr*100:.0f}%)"
    else:              sf = 0;  sfsig = f"Short flow normal ({sr*100:.0f}%)" if sr else "Date short flow indisponibile"

    si = data.get("short_interest_pct")
    si = float(si) if si is not None else None
    if si is None:   ss = 0;  shsig = "Short interest indisponibil"
    elif si > 30:    ss = 20; shsig = f"Short interest foarte ridicat ({si:.1f}%) — potențial squeeze"
    elif si > 20:    ss = 15; shsig = f"Short interest ridicat ({si:.1f}%)"
    elif si > 10:    ss = 8;  shsig = f"Short interest elevat ({si:.1f}%)"
    elif si > 5:     ss = 3;  shsig = f"Short interest moderat ({si:.1f}%)"
    else:            ss = 0;  shsig = f"Short interest redus ({si:.1f}%)"

    so    = int(data.get("score_ownership") or 0)
    total = max(0, min(100, sv + sf + ss + so))

    buys  = int(data.get("insider_buys_90d") or 0)
    sells = int(data.get("insider_sells_90d") or 0)
    bval  = float(data.get("insider_buy_value") or 0)
    sval  = float(data.get("insider_sell_value") or 0)

    parts = []
    if sv > 0:  parts.append(vsig.lower())
    if sf > 0:  parts.append(sfsig.lower())
    if ss > 0:  parts.append(shsig.lower())
    if so > 0:  parts.append(data.get("ownership_signal", "").lower())
    if buys > 0:  parts.append(f"{buys} cumpărări insider în 90 zile (info)")
    if sells > 0: parts.append(f"{sells} vânzări insider în 90 zile — monitorizează ca semnal de ieșire")
    if not parts: parts.append("niciun semnal semnificativ detectat")

    return {
        "score":                total,
        "score_volume":         sv,
        "score_insider":        0,
        "score_insider_quality": 0,
        "score_ownership":      so,
        "score_short_interest": ss,
        "score_short_flow":     sf,
        "score_fundamental":    0,
        "score_penalty":        0,
        "volume_signal":        vsig,
        "insider_signal":       f"{buys} cumpărări / {sells} vânzări (90 zile, doar informativ)",
        "short_signal":         shsig,
        "short_flow_signal":    sfsig,
        "thesis":               ". ".join(p.capitalize() for p in parts) + ".",
    }


# ── Core enrich ───────────────────────────────────────────────────────────────

def enrich_single(ticker: str, scan_data: dict | None = None) -> dict | None:
    ticker = ticker.upper().strip()
    if not ticker:
        return None

    data = {
        "ticker": ticker, "price": None, "volume": 0,
        "avg_volume_20d": 0, "vol_ratio": 0,
        "company_name": "", "sector": "", "industry": "",
        "pe_ratio": None, "market_cap": 0,
        "inst_ownership_pct": None, "beta": None,
        "insider_buys_90d": 0, "insider_buy_value": 0.0,
        "insider_sells_90d": 0, "insider_sell_value": 0.0,
        "top_insider_role": "Unknown", "insider_quality_score": 0,
        "short_interest_pct": None, "short_sale_ratio": None,
        "short_sale_volume": 0, "total_volume_reported": 0,
        "short_flow_signal": "",
        "ownership_form": "", "ownership_holder": "",
        "ownership_pct": None, "ownership_signal": "", "score_ownership": 0,
    }

    if scan_data:
        for k in ["price", "volume", "avg_volume_20d", "vol_ratio"]:
            if scan_data.get(k) is not None:
                data[k] = scan_data[k]
    else:
        data.update(get_price_volume(ticker))

    # FMP profile — singurul call FMP
    data.update(get_profile(ticker))
    time.sleep(0.3)

    # SEC EDGAR — insider Form 4 (gratuit)
    data.update(get_insider_data_edgar(ticker))
    time.sleep(0.15)

    # SEC EDGAR — 13D/13G ownership (gratuit)
    data.update(get_ownership_edgar(ticker))
    time.sleep(0.15)

    # yfinance + FINRA — short data (gratuit)
    data.update(get_short_data(ticker))

    data.update(build_signals_and_scores(data))
    return data


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []
    enriched = []
    total    = len(candidates)
    print(f"Enrich {total} candidați | FMP calls: {total} (doar profile)")

    for i, c in enumerate(candidates):
        ticker = (c.get("ticker") or "").upper().strip()
        print(f"  [{i+1}/{total}] {ticker}")
        result = enrich_single(ticker, scan_data=c)
        if result:
            enriched.append(result)

    enriched.sort(key=lambda x: x.get("score", 0), reverse=True)
    if enriched:
        top = enriched[0]
        print(f"\nTop: {top['ticker']} = {top['score']}/100 | {top.get('company_name','')}")
        print(f"Scor: vol={top.get('score_volume',0)} sf={top.get('score_short_flow',0)} "
              f"si={top.get('score_short_interest',0)} own={top.get('score_ownership',0)}")
    return enriched


def enrich_watchlist(watchlist_tickers: list[str],
                     scan_results: list[dict]) -> list[dict]:
    if not watchlist_tickers:
        return []
    scan_map = {r.get("ticker","").upper(): r for r in (scan_results or [])}
    enriched = []
    total    = len(watchlist_tickers)
    print(f"Enrich watchlist: {total} tickers | FMP calls: {total}")

    for i, ticker in enumerate(watchlist_tickers):
        ticker = ticker.upper().strip()
        src    = "scan" if ticker in scan_map else "watchlist-only"
        print(f"  [{i+1}/{total}] {ticker} ({src})")
        result = enrich_single(ticker, scan_data=scan_map.get(ticker))
        if result:
            enriched.append(result)

    return enriched


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if not candidates:
        print("Niciun candidat azi"); sys.exit(0)
    enriched = enrich_candidates(candidates)
    if enriched:
        save_enriched(enriched)
        print(f"\nSalvat {len(enriched)} tickers")
        for e in enriched[:10]:
            print(f"  {e['ticker']:<8} score={e['score']:>3}/100  "
                  f"vol={e.get('score_volume',0):>2}  "
                  f"sf={e.get('score_short_flow',0):>2}  "
                  f"si={e.get('score_short_interest',0):>2}  "
                  f"own={e.get('score_ownership',0):>2}  "
                  f"{e.get('company_name','')[:25]}")
