"""
Orchestrator — apelat de GitHub Actions cu --phase argument.
"""
import argparse
import sys
from datetime import datetime

sys.path.insert(0, ".")


def run_universe():
    print(f"[{datetime.utcnow().isoformat()}] Faza: UNIVERSE BUILD")
    from collectors.universe_builder import build_universe
    from app.db import save_universe
    universe = build_universe()
    if not universe:
        print("FAIL: Universe gol")
        sys.exit(1)
    save_universe(universe)
    print(f"OK: {len(universe)} tickers salvați")


def run_scan():
    print(f"[{datetime.utcnow().isoformat()}] Faza: SCAN")
    from collectors.scanner import run_scan as do_scan
    from app.db import get_universe, save_scan_results
    universe = get_universe()
    if not universe:
        print("FAIL: Universe gol — rulează universe primul")
        sys.exit(1)
    tickers = [u["ticker"] for u in universe]
    results = do_scan(tickers)
    if results:
        save_scan_results(results)
        print(f"OK: {len(results)} candidați salvați")
    else:
        print("OK: Niciun candidat azi")


def run_enrich():
    print(f"[{datetime.utcnow().isoformat()}] Faza: ENRICH")
    from collectors.enricher import enrich_candidates
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if not candidates:
        print("SKIP: Niciun candidat de enriched")
        sys.exit(0)
    enriched = enrich_candidates(candidates)
    if enriched:
        save_enriched(enriched)
        print(f"OK: {len(enriched)} tickers salvați")


PHASES = {"universe": run_universe, "scan": run_scan, "enrich": run_enrich}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=list(PHASES.keys()), required=True)
    args = parser.parse_args()
    print(f"=== Smart Money Screener | {args.phase.upper()} ===")
    PHASES[args.phase]()
    print("=== DONE ===")
