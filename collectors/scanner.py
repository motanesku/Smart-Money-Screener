"""
Scan zilnic dimineața — detectează volume spikes în univers.
Sursa: yfinance bulk download — 1 singur call pentru tot universul.
"""
import sys
import yfinance as yf

MIN_VOL_RATIO = 2.0
MIN_PRICE     = 5.0
TOP_N         = 50


def run_scan(tickers: list[str]) -> list[dict]:
    if not tickers:
        print("EROARE: Lista tickers goală")
        return []

    print(f"Scan pentru {len(tickers)} tickers...")

    raw = yf.download(
        tickers=tickers,
        period="25d",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    candidates = []
    for ticker in tickers:
        try:
            hist = raw[ticker] if len(tickers) > 1 else raw
            if hist is None or len(hist) < 5:
                continue
            hist = hist.dropna(subset=["Volume", "Close"])
            if len(hist) < 5:
                continue

            price      = float(hist["Close"].iloc[-1])
            vol_today  = float(hist["Volume"].iloc[-1])
            if price < MIN_PRICE or vol_today == 0:
                continue

            avg_vol = float(hist["Volume"].iloc[:-1].tail(20).mean())
            if avg_vol < 10_000:
                continue

            vol_ratio = vol_today / avg_vol
            if vol_ratio >= MIN_VOL_RATIO:
                candidates.append({
                    "ticker":        ticker,
                    "price":         round(price, 2),
                    "volume":        int(vol_today),
                    "avg_volume_20d": int(avg_vol),
                    "vol_ratio":     round(vol_ratio, 2),
                })
        except Exception:
            continue

    candidates.sort(key=lambda x: x["vol_ratio"], reverse=True)
    result = candidates[:TOP_N]
    print(f"Găsiți {len(result)} candidați (vol_ratio >= {MIN_VOL_RATIO}x)")
    return result


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_universe, save_scan_results
    universe = get_universe()
    if not universe:
        print("EROARE: Universe gol — rulează universe_builder primul")
        sys.exit(1)
    tickers = [u["ticker"] for u in universe]
    results = run_scan(tickers)
    if results:
        save_scan_results(results)
        print("\nTop 10:")
        for r in results[:10]:
            print(f"  {r['ticker']:<8} ${r['price']:<8} {r['vol_ratio']}x")
