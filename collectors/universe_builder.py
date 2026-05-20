"""
Universe Builder v2 — fără FMP, fără API key extern.

Surse:
  S&P 500   → Wikipedia (company_name, sector, industry)
  NASDAQ 100 → Wikipedia
  S&P MidCap 400 → Wikipedia

Filtru:
  avg_volume_20d > 500,000 acțiuni (din yfinance batch OHLCV 30d)
  Market cap > $300M — implicit prin apartenența la index

Rulează duminică (cron săptămânal).
"""
import sys
import time
import requests
import pandas as pd
import yfinance as yf

HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; SmartMoneyScreener/2.0)"}
MIN_AVG_VOL = 500_000


# ── Wikipedia parsers ─────────────────────────────────────────

def _parse_wiki_index(url: str, index_name: str,
                      ticker_hints: list[str],
                      name_hints: list[str],
                      sector_hints: list[str]) -> list[dict]:
    """
    Generic Wikipedia index parser.
    Caută primul tabel care conține cel puțin 50 de rânduri cu ticker-uri valide.
    Compatibil cu pandas 2.x (folosește io.StringIO).
    """
    import io

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"  [{index_name}] EROARE download: {e}")
        return []

    # pandas 2.x necesită StringIO; încearcă mai mulți parseri
    for parser in ["lxml", "html.parser", "html5lib"]:
        try:
            tables = pd.read_html(io.StringIO(html), flavor=parser)
            break
        except Exception:
            tables = []
            continue

    if not tables:
        print(f"  [{index_name}] EROARE: niciun tabel HTML găsit")
        return []

    # Colectează toți candidații, returnează tabelul cu cele mai multe tickers
    all_candidates: list[list[dict]] = []

    for t_idx, df in enumerate(tables[:10]):
        if len(df) < 20:
            continue

        # Aplatizează MultiIndex columns (ex: ('Added','Ticker') → 'Added Ticker')
        if hasattr(df.columns, "levels"):
            df.columns = [
                " ".join(str(lvl) for lvl in col if str(lvl) not in ("", "nan")).strip()
                for col in df.columns
            ]
        else:
            df.columns = [str(c) for c in df.columns]

        cols = list(df.columns)

        def _find_col(hints):
            return next(
                (c for c in cols if any(h.lower() in c.lower() for h in hints)),
                None
            )

        ticker_col   = _find_col(ticker_hints)
        if ticker_col is None:
            continue

        name_col     = _find_col(name_hints)
        sector_col   = _find_col(sector_hints)
        industry_col = _find_col(["sub-industry", "sub industry"])
        if industry_col is None:
            industry_col = _find_col(["industry"])

        results = []
        for _, row in df.iterrows():
            raw    = str(row[ticker_col]).strip()
            ticker = raw.replace(".", "-").upper()
            if (not ticker or len(ticker) > 6 or
                    ticker in ("NAN", "TICKER", "SYMBOL", "N/A", "-")):
                continue
            if not ticker.replace("-", "").isalpha():
                continue

            results.append({
                "ticker":       ticker,
                "company_name": str(row[name_col]).strip()     if name_col     else "",
                "sector":       str(row[sector_col]).strip()   if sector_col   else "",
                "industry":     str(row[industry_col]).strip() if industry_col else "",
                "index_member": index_name,
                "market_cap":   0,
                "avg_volume":   0,
            })

        if len(results) >= 20:
            all_candidates.append(results)

    # Returnează tabelul cu cele mai multe tickers valide
    if all_candidates:
        best = max(all_candidates, key=len)
        print(f"  [{index_name}] {len(best)} tickers")
        return best

    print(f"  [{index_name}] AVERTISMENT: niciun tabel valid găsit — verifică structura paginii Wikipedia")
    return []


def get_sp500() -> list[dict]:
    return _parse_wiki_index(
        url="https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        index_name="SP500",
        ticker_hints=["Symbol", "Ticker"],
        name_hints=["Security", "Company", "Name"],
        sector_hints=["GICS Sector", "Sector"],
    )


def get_nasdaq100() -> list[dict]:
    return _parse_wiki_index(
        url="https://en.wikipedia.org/wiki/Nasdaq-100",
        index_name="NDX100",
        ticker_hints=["Ticker", "Symbol"],
        name_hints=["Company", "Security", "Name"],
        sector_hints=["GICS Sector", "Sector"],
    )


def get_sp400() -> list[dict]:
    return _parse_wiki_index(
        url="https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
        index_name="SP400",
        ticker_hints=["Ticker symbol", "Ticker", "Symbol"],
        name_hints=["Company", "Security", "Name"],
        sector_hints=["GICS Sector", "Sector"],
    )


# ── Volume enrichment ─────────────────────────────────────────

def _enrich_with_volume(tickers: list[str], batch_size: int = 100) -> dict[str, int]:
    """
    Batch download 30 de zile OHLCV.
    Returnează {ticker: avg_volume_20d}.
    """
    vol_map: dict[str, int] = {}
    total_batches = (len(tickers) + batch_size - 1) // batch_size
    print(f"  Volume enrich: {len(tickers)} tickers în {total_batches} batch-uri...")

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
            print(f"  Batch {i // batch_size + 1}/{total_batches} eroare: {e}")

        if i + batch_size < len(tickers):
            time.sleep(0.5)

    return vol_map


# ── Main ──────────────────────────────────────────────────────

def build_universe() -> list[dict]:
    print("=== Universe Builder v2 ===")

    print("Step 1: Descarcă indici din Wikipedia...", flush=True)
    sp500  = get_sp500()
    print(f"  SP500 raw: {len(sp500)}", flush=True)
    ndx100 = get_nasdaq100()
    print(f"  NDX100 raw: {len(ndx100)}", flush=True)
    sp400  = get_sp400()
    print(f"  SP400 raw: {len(sp400)}", flush=True)

    # Dedup: SP500 > NDX100 > SP400 (prioritate pentru sector/name)
    seen: dict[str, dict] = {}
    for batch in [sp500, ndx100, sp400]:
        for item in batch:
            t = item["ticker"]
            if t not in seen:
                seen[t] = item

    all_items  = list(seen.values())
    all_tickers = [t["ticker"] for t in all_items]
    print(f"  Total unic: {len(all_items)} tickers")

    print("Step 2: Enrich cu avg_volume din yfinance...")
    vol_map = _enrich_with_volume(all_tickers)

    print("Step 3: Filtrare avg_volume > {:,}...".format(MIN_AVG_VOL))
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
    print(f"  SP500: {sum(1 for u in universe if u['index_member'] == 'SP500')}")
    print(f"  NDX100: {sum(1 for u in universe if u['index_member'] == 'NDX100')}")
    print(f"  SP400: {sum(1 for u in universe if u['index_member'] == 'SP400')}")
    return universe


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import save_universe, get_client

    universe = build_universe()
    if not universe:
        print("EROARE: Universe gol")
        sys.exit(1)

    # Curăță records vechi fără index_member (rămășițe din versiuni anterioare)
    try:
        get_client().table("universe").delete().eq("index_member", "").execute()
        print("Curățat records legacy (index_member gol)")
    except Exception as e:
        print(f"  Curățare legacy: {e}")

    save_universe(universe)
    print(f"\nSalvat {len(universe)} tickers în Supabase")
    for u in universe[:5]:
        print(f"  {u['ticker']:<8}  {u['index_member']:<7}  vol={u['avg_volume']:>12,}  {u['sector']}")
