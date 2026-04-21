"""
Scan zilnic de dimineata: identifica tickers cu volume spike din universe.
Foloseste yfinance bulk download — 1 singur call pentru toti tickerii.
Output: top 50 candidati sortati dupa vol_ratio.
"""
import sys
import yfinance as yf
import pandas as pd
from datetime import date


MIN_VOL_RATIO = 2.0      # volumul de azi trebuie sa fie 2x media 20 zile
MIN_PRICE = 5.0          # ignore tickers sub $5
TOP_N = 50               # returneaza primii 50 candidati


def run_scan(tickers: list[str]) -> list[dict]:
    """
    Descarca ultimele 25 de zile pentru toti tickerii dintr-un bulk call.
    Calculeaza vol_ratio = vol_azi / avg_vol_20d.
    """
    if not tickers:
        print("EROARE: Lista de tickers goala")
        return []

    print(f"Scan pentru {len(tickers)} tickers...")

    # 1 singur call pentru tot universul
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
            if len(tickers) == 1:
                hist = raw
            else:
                hist = raw[ticker]

            # Verifica sa avem date suficiente
            if hist is None or len(hist) < 5:
                continue

            hist = hist.dropna(subset=["Volume", "Close"])
            if len(hist) < 5:
                continue

            today_row = hist.iloc[-1]
            price = float(today_row["Close"])
            vol_today = float(today_row["Volume"])

            if price < MIN_PRICE or vol_today == 0:
                continue

            # Media pe ultimele 20 zile (exclud ziua de azi)
            avg_vol_20d = float(hist["Volume"].iloc[:-1].tail(20).mean())

            if avg_vol_20d < 10_000:  # tickers fara lichiditate reala
                continue

            vol_ratio = vol_today / avg_vol_20d

            if vol_ratio >= MIN_VOL_RATIO:
                candidates.append({
                    "ticker": ticker,
                    "price": round(price, 2),
                    "volume": int(vol_today),
                    "avg_volume_20d": int(avg_vol_20d),
                    "vol_ratio": round(vol_ratio, 2),
                })

        except Exception:
            continue

    candidates.sort(key=lambda x: x["vol_ratio"], reverse=True)
    result = candidates[:TOP_N]
    print(f"Gasiti {len(result)} candidati (vol_ratio >= {MIN_VOL_RATIO}x)")
    return result


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_universe, save_scan_results

    universe = get_universe()
    if not universe:
        print("EROARE: Universe gol — ruleaza universe_builder.py primul")
        sys.exit(1)

    tickers = [u["ticker"] for u in universe]
    results = run_scan(tickers)

    if results:
        save_scan_results(results)
        print(f"\nTop 10 candidati:")
        for r in results[:10]:
            print(f"  {r['ticker']:<8} ${r['price']:<8} vol_ratio: {r['vol_ratio']}x")
    else:
        print("Niciun candidat gasit azi")
