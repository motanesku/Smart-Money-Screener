"""
Scanner v11 — Detectează volume spikes și calculează Relative Strength față de Sector.
"""
import sys
import yfinance as yf
import pandas as pd

MIN_VOL_RATIO = 2.0
MIN_PRICE     = 5.0
TOP_N         = 50

# Mapare ETF-uri pentru rotație sectorială
SECTOR_ETFS = {
    "Energy": "XLE", "Technology": "XLK", "Financials": "XLF",
    "Health Care": "XLV", "Consumer Defensive": "XLP", "Utilities": "XLU",
    "Communication Services": "XLC", "Industrials": "XLI", "Basic Materials": "XLB",
    "Real Estate": "XLRE", "Consumer Cyclical": "XLY"
}

def run_scan(tickers: list[str]) -> list[dict]:
    if not tickers:
        return []

    print(f"Scan v2 pentru {len(tickers)} tickers + Sector Analysis...")

    # 1. Download Bulk Tickers
    raw = yf.download(tickers, period="25d", interval="1d", group_by="ticker", threads=True, progress=False)
    
    # 2. Download Sector Data pentru Relative Strength
    sector_symbols = list(set(SECTOR_ETFS.values()))
    sectors_raw = yf.download(sector_symbols, period="2d", interval="1d", progress=False)['Close']

    candidates = []
    for ticker in tickers:
        try:
            hist = raw[ticker] if len(tickers) > 1 else raw
            hist = hist.dropna(subset=["Volume", "Close"])
            if len(hist) < 5: continue

            price = float(hist["Close"].iloc[-1])
            prev_price = float(hist["Close"].iloc[-2])
            vol_today = float(hist["Volume"].iloc[-1])
            avg_vol = float(hist["Volume"].iloc[:-1].tail(20).mean())

            if avg_vol < 10000: continue
            vol_ratio = vol_today / avg_vol

            if vol_ratio >= MIN_VOL_RATIO and price >= MIN_PRICE:
                # Calcul performanță ticker (azi)
                perf_ticker = (price / prev_price) - 1
                
                candidates.append({
                    "ticker": ticker,
                    "price": round(price, 2),
                    "volume": int(vol_today),
                    "avg_volume_20d": int(avg_vol),
                    "vol_ratio": round(vol_ratio, 2),
                    "raw_perf": perf_ticker # Va fi procesat în enricher
                })
        except: continue

    candidates.sort(key=lambda x: x["vol_ratio"], reverse=True)
    return candidates[:TOP_N]

if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_universe, save_scan_results
    u = get_universe()
    if u:
        res = run_scan([x['ticker'] for x in u])
        save_scan_results(res)
