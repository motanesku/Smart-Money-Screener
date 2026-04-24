"""
Orchestrator v9 — 4 faze:
  universe  → duminică 20:00 UTC
  scan      → 08:00 ET zilnic
  enrich    → 08:45 ET + 16:30 ET (candidații din scan)
  watchlist → 16:45 ET zilnic (toți tickerii din watchlist, indiferent de scan)
"""
import argparse, sys
from datetime import datetime

sys.path.insert(0, ".")


def run_universe():
    print(f"[{datetime.utcnow().isoformat()}] UNIVERSE BUILD")
    from collectors.universe_builder import build_universe
    from app.db import save_universe
    universe = build_universe()
    if not universe:
        print("FAIL: Universe gol"); sys.exit(1)
    save_universe(universe)
    print(f"OK: {len(universe)} tickers")


def run_scan():
    print(f"[{datetime.utcnow().isoformat()}] SCAN")
    from collectors.scanner import run_scan as do_scan
    from app.db import get_universe, save_scan_results
    universe = get_universe()
    if not universe:
        print("FAIL: Universe gol — rulează universe primul"); sys.exit(1)
    tickers = [u["ticker"] for u in universe]
    results = do_scan(tickers)
    if results:
        save_scan_results(results)
        print(f"OK: {len(results)} candidați")
    else:
        print("OK: Niciun candidat azi")


def run_enrich():
    print(f"[{datetime.utcnow().isoformat()}] ENRICH (scan candidates)")
    from collectors.enricher import enrich_candidates
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if not candidates:
        print("SKIP: Niciun candidat de enriched"); sys.exit(0)
    enriched = enrich_candidates(candidates)
    if enriched:
        save_enriched(enriched)
        print(f"OK: {len(enriched)} tickers salvați")


def run_watchlist():
    """
    Enrich zilnic pentru toți tickerii din watchlist.
    Independent de scan — include tickeri adăugați manual.
    Folosește datele din scan dacă tickerul a apărut și acolo.
    """
    print(f"[{datetime.utcnow().isoformat()}] WATCHLIST ENRICH")
    from collectors.enricher import enrich_watchlist
    from app.db import get_watchlist, get_scan_results, save_enriched

    watchlist = get_watchlist()
    if not watchlist:
        print("SKIP: Watchlist gol"); sys.exit(0)

    tickers      = [w["ticker"] for w in watchlist]
    scan_results = get_scan_results(days_back=1)

    print(f"Watchlist: {len(tickers)} tickers | Scan results disponibile: {len(scan_results)}")
    enriched = enrich_watchlist(tickers, scan_results)

    if enriched:
        save_enriched(enriched)
        print(f"OK: {len(enriched)} tickers watchlist salvați")
    else:
        print("WARNING: Niciun ticker enriched")


PHASES = {
    "universe":  run_universe,
    "scan":      run_scan,
    "enrich":    run_enrich,
    "watchlist": run_watchlist,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=list(PHASES.keys()), required=True)
    args = parser.parse_args()
    print(f"=== Smart Money Screener | {args.phase.upper()} ===")
    PHASES[args.phase]()
    print("=== DONE ===")
