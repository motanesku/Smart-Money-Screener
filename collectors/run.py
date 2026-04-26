"""
Orchestrator v10 — transmite universe la run_scan pentru RS și Sector Heat Score.
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
    # FIX: transmite universe pentru RS și Sector Heat Score
    results = do_scan(tickers, universe=universe)
    if results:
        save_scan_results(results)
        print(f"OK: {len(results)} candidați")
    else:
        print("OK: Niciun candidat azi")


def run_enrich():
    print(f"[{datetime.utcnow().isoformat()}] ENRICH")
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
    print(f"[{datetime.utcnow().isoformat()}] WATCHLIST ENRICH")
    from collectors.enricher import enrich_watchlist
    from app.db import get_watchlist, get_scan_results, save_enriched
    watchlist = get_watchlist()
    if not watchlist:
        print("SKIP: Watchlist gol"); sys.exit(0)
    tickers      = [w["ticker"] for w in watchlist]
    scan_results = get_scan_results(days_back=1)
    print(f"Watchlist: {len(tickers)} tickers | Scan disponibil: {len(scan_results)}")
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
