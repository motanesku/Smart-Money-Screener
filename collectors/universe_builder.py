"""
Universe Builder v3 — ETF Holdings oficiale (fără Wikipedia, fără API key)

Surse autoritare, actualizate zilnic de administratorii indicilor:
  S&P 500    → SPY holdings (State Street SSGA)
  S&P 400    → MDY holdings (State Street SSGA)
  NASDAQ 100 → QQQ holdings (Invesco)

Include ticker, company_name, sector GICS, industry.
Filtru: avg_volume_20d > 500,000 acțiuni (din yfinance batch OHLCV).

Rulează duminică (cron săptămânal).
"""
import io
import sys
import time

import pandas as pd
import requests
import yfinance as yf

MIN_AVG_VOL = 500_000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ── Descărcări ETF Holdings ───────────────────────────────────

def _get_spy_holdings() -> list[dict]:
    """
    S&P 500 din SPY ETF holdings (State Street SSGA).
    URL-ul returnează un Excel cu holdings-urile zilnice.
    """
    url = (
        "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
        "holdings-daily-us-en-spy.xlsx"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        df = pd.read_excel(io.BytesIO(resp.content), skiprows=4, engine="openpyxl")

        # Coloane tipice: Name | Ticker | Identifier | SEDOL | Weight |
        #                 Shares Held | Local Market Value | ...
        results = _parse_ssga_holdings(df, "SP500")
        print(f"  [SP500/SPY] {len(results)} tickers")
        return results
    except Exception as e:
        print(f"  [SP500/SPY] EROARE: {e}")
        return []


def _get_mdy_holdings() -> list[dict]:
    """
    S&P MidCap 400 din MDY ETF holdings (State Street SSGA).
    """
    url = (
        "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
        "holdings-daily-us-en-mdy.xlsx"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        df = pd.read_excel(io.BytesIO(resp.content), skiprows=4, engine="openpyxl")
        results = _parse_ssga_holdings(df, "SP400")
        print(f"  [SP400/MDY] {len(results)} tickers")
        return results
    except Exception as e:
        print(f"  [SP400/MDY] EROARE: {e}")
        return []


def _get_qqq_holdings() -> list[dict]:
    """
    NASDAQ 100 din QQQ ETF holdings (Invesco).
    """
    url = (
        "https://www.invesco.com/us/financial-products/etfs/holdings/main/"
        "holdings/0?audienceType=Investor&action=download&ticker=QQQ"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), skiprows=4)
        results = _parse_invesco_holdings(df, "NDX100")
        print(f"  [NDX100/QQQ] {len(results)} tickers")
        return results
    except Exception as e:
        print(f"  [NDX100/QQQ] EROARE: {e}")
        return []


def _parse_ssga_holdings(df: pd.DataFrame, index_name: str) -> list[dict]:
    """
    Parser pentru fișierele SSGA (SPY, MDY).
    Coloane relevante: Name, Ticker, Sector (dacă există).
    """
    # Normalizează numele coloanelor
    df.columns = [str(c).strip() for c in df.columns]

    # Găsește coloana cu ticker-uri
    ticker_col = _find_col(df.columns, ["Ticker", "Symbol", "Identifier"])
    name_col   = _find_col(df.columns, ["Name", "Security", "Description"])
    sector_col = _find_col(df.columns, ["Sector", "GICS"])

    if not ticker_col:
        return []

    results = []
    for _, row in df.iterrows():
        ticker = str(row[ticker_col]).strip().upper()
        # Exclude cash, futures, sau linii invalide
        if (not ticker or len(ticker) > 6 or
                not ticker.replace("-", "").isalpha() or
                ticker in ("NAN", "-", "TICKER")):
            continue

        results.append({
            "ticker":       ticker,
            "company_name": str(row[name_col]).strip() if name_col else "",
            "sector":       str(row[sector_col]).strip() if sector_col else "",
            "industry":     "",
            "index_member": index_name,
            "market_cap":   0,
            "avg_volume":   0,
        })

    return results


def _parse_invesco_holdings(df: pd.DataFrame, index_name: str) -> list[dict]:
    """
    Parser pentru fișierele Invesco (QQQ).
    Coloane relevante: Name, Ticker, Sector.
    """
    df.columns = [str(c).strip() for c in df.columns]

    ticker_col = _find_col(df.columns, ["Ticker", "Symbol", "Security Identifier"])
    name_col   = _find_col(df.columns, ["Name", "Security", "Holding"])
    sector_col = _find_col(df.columns, ["Sector", "GICS"])

    if not ticker_col:
        return []

    results = []
    for _, row in df.iterrows():
        ticker = str(row[ticker_col]).strip().upper()
        if (not ticker or len(ticker) > 6 or
                not ticker.replace("-", "").isalpha() or
                ticker in ("NAN", "-", "TICKER")):
            continue

        results.append({
            "ticker":       ticker,
            "company_name": str(row[name_col]).strip() if name_col else "",
            "sector":       str(row[sector_col]).strip() if sector_col else "",
            "industry":     "",
            "index_member": index_name,
            "market_cap":   0,
            "avg_volume":   0,
        })

    return results


def _find_col(columns, hints: list[str]) -> str | None:
    """Găsește prima coloană care conține unul din hints (case-insensitive)."""
    for col in columns:
        if any(h.lower() in col.lower() for h in hints):
            return col
    return None


# ── Sector enrichment din yfinance ───────────────────────────

def _enrich_sector(items: list[dict], batch_size: int = 20) -> list[dict]:
    """
    Completează sector + industry + company_name din yfinance.info
    pentru tickerii cu sector lipsă.
    Rulează doar la universe build (o dată/săptămână) — ~4 minute pentru 900 tickers.
    """
    missing = [x for x in items if not x.get("sector") or x["sector"] in ("", "-", "nan")]
    if not missing:
        return items

    print(f"  Sector lipsă: {len(missing)} tickers → enrich din yfinance...")
    sector_map: dict[str, dict] = {}
    total = (len(missing) + batch_size - 1) // batch_size

    for i in range(0, len(missing), batch_size):
        batch = missing[i: i + batch_size]
        for item in batch:
            sym = item["ticker"]
            try:
                info = yf.Ticker(sym).info
                sector_map[sym] = {
                    "sector":       info.get("sector")   or "",
                    "industry":     info.get("industry") or "",
                    "company_name": info.get("longName") or item.get("company_name") or "",
                }
            except Exception:
                sector_map[sym] = {"sector": "", "industry": "", "company_name": ""}

        done = min(i + batch_size, len(missing))
        print(f"  Sector enrich: {done}/{len(missing)}", end="\r", flush=True)

        if i + batch_size < len(missing):
            time.sleep(0.5)

    print()  # newline după \r

    # Aplică îmbogățirile
    for item in items:
        sym = item["ticker"]
        if sym in sector_map:
            enr = sector_map[sym]
            if enr["sector"]:
                item["sector"] = enr["sector"]
            if enr["industry"]:
                item["industry"] = enr["industry"]
            if enr["company_name"] and not item.get("company_name"):
                item["company_name"] = enr["company_name"]

    return items


# ── Volume enrichment din yfinance ───────────────────────────

def _enrich_with_volume(tickers: list[str], batch_size: int = 100) -> dict[str, int]:
    """
    Batch download 30 de zile OHLCV.
    Returnează {ticker: avg_volume_20d}.
    """
    vol_map: dict[str, int] = {}
    total = (len(tickers) + batch_size - 1) // batch_size
    print(f"  Volume enrich: {len(tickers)} tickers în {total} batch-uri...")

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i: i + batch_size]
        try:
            raw = yf.download(
                batch,
                period="30d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
            for ticker in batch:
                try:
                    if len(batch) == 1:
                        hist = raw
                    elif hasattr(raw.columns, "levels"):
                        if ticker not in raw.columns.get_level_values(0):
                            continue
                        hist = raw[ticker]
                    else:
                        continue
                    vol = hist["Volume"].dropna()
                    if len(vol) >= 5:
                        vol_map[ticker] = int(vol.tail(20).mean())
                except Exception:
                    pass
        except Exception as e:
            print(f"  Batch {i // batch_size + 1}/{total} eroare: {e}")

        if i + batch_size < len(tickers):
            time.sleep(0.5)

    return vol_map


# ── Main ──────────────────────────────────────────────────────

def build_universe() -> list[dict]:
    print("=== Universe Builder v3 (ETF Holdings) ===")

    print("Step 1: Descarcă ETF holdings (SPY / MDY / QQQ)...")
    sp500  = _get_spy_holdings()
    sp400  = _get_mdy_holdings()
    ndx100 = _get_qqq_holdings()

    print(f"  SP500 raw: {len(sp500)}", flush=True)
    print(f"  SP400 raw: {len(sp400)}", flush=True)
    print(f"  NDX100 raw: {len(ndx100)}", flush=True)

    # Dedup: SP500 > SP400 > NDX100 (SP500 are prioritate pt sector data)
    seen: dict[str, dict] = {}
    for batch in [sp500, sp400, ndx100]:
        for item in batch:
            t = item["ticker"]
            if t not in seen:
                seen[t] = item

    all_items   = list(seen.values())
    all_tickers = [t["ticker"] for t in all_items]
    print(f"  Total unic: {len(all_items)} tickers")

    print("Step 2: Enrich sector + industry din yfinance...")
    all_items = _enrich_sector(all_items)

    print("Step 3: Enrich cu avg_volume din yfinance...")
    vol_map = _enrich_with_volume(all_tickers)

    print(f"Step 4: Filtrare avg_volume > {MIN_AVG_VOL:,}...")
    universe, filtered = [], 0
    for item in all_items:
        avg_vol = vol_map.get(item["ticker"], 0)
        if avg_vol < MIN_AVG_VOL:
            filtered += 1
            continue
        item["avg_volume"] = avg_vol
        universe.append(item)

    universe.sort(key=lambda x: x["avg_volume"], reverse=True)

    print(f"\nUniverse final: {len(universe)} tickers")
    print(f"  Filtrate (vol < {MIN_AVG_VOL:,}): {filtered}")
    for idx in ["SP500", "SP400", "NDX100"]:
        n = sum(1 for u in universe if u["index_member"] == idx)
        s = sum(1 for u in universe if u["index_member"] == idx and u.get("sector", ""))
        print(f"  {idx}: {n} tickers, {s} cu sector")

    return universe


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import save_universe, get_client

    universe = build_universe()
    if not universe:
        print("EROARE: Universe gol")
        sys.exit(1)

    # Curăță records vechi fără index_member
    try:
        db = get_client()
        db.table("universe").delete().eq("index_member", "").execute()
        db.table("universe").delete().is_("index_member", "null").execute()
        print("Curățat records legacy")
    except Exception as e:
        print(f"  Curățare legacy: {e}")

    save_universe(universe)
    print(f"\nSalvat {len(universe)} tickers în Supabase")
    for u in universe[:5]:
        print(f"  {u['ticker']:<8} {u['index_member']:<7} "
              f"vol={u['avg_volume']:>12,}  {u['sector']}")
