"""
Orchestrator v2 — Witness-Based Scanner

Faze:
  universe  → universe_builder.build_universe() + save
  scan      → scanner.run_scan() — face tot (scan + enrich în unul)
  watchlist → enrichment suplimentar pentru tickerii din watchlist

Eliminat: faza 'enrich' (acum integrată în 'scan').
"""
import argparse
import sys
from datetime import datetime

sys.path.insert(0, ".")


def run_universe():
    print(f"[{datetime.utcnow().isoformat()}] UNIVERSE BUILD")
    from collectors.universe_builder import build_universe
    from app.db import save_universe

    universe = build_universe()
    if not universe:
        print("FAIL: Universe gol")
        sys.exit(1)
    save_universe(universe)
    print(f"OK: {len(universe)} tickers salvați")


def run_scan():
    print(f"[{datetime.utcnow().isoformat()}] SCAN + ENRICH (v2)")
    from collectors.scanner import run_scan as do_scan

    results = do_scan()
    print(f"OK: {len(results)} tickers cu semnal activ")


def run_watchlist():
    """
    Rulează scan pe tickerii din watchlist dacă nu au fost prinși în scan-ul zilnic.
    Util pentru monitorizare continuă a pozițiilor urmărite.
    """
    print(f"[{datetime.utcnow().isoformat()}] WATCHLIST ENRICH")
    from app.db import get_watchlist, get_enriched_v2, save_enriched_v2
    from collectors.scanner import analyze_ticker, SECTOR_ETFS
    import yfinance as yf
    import pandas as pd

    watchlist = get_watchlist()
    if not watchlist:
        print("SKIP: Watchlist gol")
        return

    # Verifică ce tickers nu sunt deja în enriched_v2 azi
    today_enriched  = {r["ticker"] for r in get_enriched_v2(days_back=1)}
    missing_tickers = [w["ticker"] for w in watchlist if w["ticker"] not in today_enriched]

    if not missing_tickers:
        print("OK: Toți tickerii din watchlist sunt deja în enriched_v2 azi")
        return

    print(f"  Enrich watchlist: {len(missing_tickers)} tickers lipsă din scan")

    # Download ETFs
    etf_symbols = list(set(SECTOR_ETFS.values()))
    try:
        etf_raw    = yf.download(etf_symbols, period="1y", auto_adjust=True, progress=False)
        etf_closes = etf_raw["Close"] if hasattr(etf_raw.columns, "levels") else pd.DataFrame()
    except Exception:
        etf_closes = pd.DataFrame()

    from app.db import get_universe
    universe   = get_universe()
    sector_map = {u["ticker"]: u.get("sector", "")       for u in universe}
    name_map   = {u["ticker"]: u.get("company_name", "")  for u in universe}
    cap_map    = {u["ticker"]: int(u.get("market_cap", 0)) for u in universe}

    results = []
    for ticker in missing_tickers:
        try:
            raw  = yf.download(ticker, period="1y", auto_adjust=True, progress=False)
            hist = raw.dropna(how="all")
            res  = analyze_ticker(
                ticker, hist, etf_closes,
                sector_map.get(ticker, ""),
                name_map.get(ticker, ""),
                cap_map.get(ticker, 0),
            )
            if res:
                results.append(res)
        except Exception as e:
            print(f"  {ticker}: {e}")

    if results:
        save_enriched_v2(results)
        print(f"OK: {len(results)} tickers watchlist salvați")
    else:
        print("WARNING: Niciun ticker watchlist enriched")


PHASES = {
    "universe":  run_universe,
    "scan":      run_scan,
    "watchlist": run_watchlist,
}

ALL_PHASES = ["universe", "scan", "watchlist"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=list(PHASES.keys()) + ["all"],
        required=True,
        help="Faza de rulat: universe | scan | watchlist | all",
    )
    args = parser.parse_args()

    phases_to_run = ALL_PHASES if args.phase == "all" else [args.phase]
    for phase in phases_to_run:
        print(f"\n=== Smart Money Screener v2 | {phase.upper()} ===")
        PHASES[phase]()
        print(f"=== {phase.upper()} DONE ===")

    print("\n=== ALL DONE ===")
