"""
Scanner v12 — implementează complet arhitectura v2:
- Sector Heat Score: câte companii/sector au vol spike → "In Play" dacă >= 5
- Relative Strength vs ETF sector (rs_vs_sector)
- Returnează câmpurile noi în fiecare candidat
"""
import sys
import yfinance as yf
import pandas as pd

MIN_VOL_RATIO = 2.0
MIN_PRICE     = 5.0
TOP_N         = 50

SECTOR_ETFS = {
    "Energy":                "XLE",
    "Technology":            "XLK",
    "Financials":            "XLF",
    "Health Care":           "XLV",
    "Consumer Defensive":    "XLP",
    "Utilities":             "XLU",
    "Communication Services":"XLC",
    "Industrials":           "XLI",
    "Basic Materials":       "XLB",
    "Real Estate":           "XLRE",
    "Consumer Cyclical":     "XLY",
}


def _download_etf_perfs() -> dict[str, float]:
    """
    Descarcă performanța zilnică a tuturor ETF-urilor sectoriale.
    Returnează: {"XLE": 0.012, "XLK": -0.005, ...}
    """
    etf_tickers = list(SECTOR_ETFS.values())
    try:
        raw = yf.download(
            tickers=etf_tickers,
            period="3d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        perfs = {}
        for etf in etf_tickers:
            try:
                hist = raw[etf] if len(etf_tickers) > 1 else raw
                hist = hist.dropna(subset=["Close"])
                if len(hist) >= 2:
                    perfs[etf] = float(hist["Close"].iloc[-1] / hist["Close"].iloc[-2]) - 1
            except Exception:
                pass
        return perfs
    except Exception as e:
        print(f"  [scanner] ETF download eroare: {e}")
        return {}


def run_scan(tickers: list[str], universe: list[dict] | None = None) -> list[dict]:
    """
    Args:
        tickers:  lista de simboluri de scanat
        universe: lista de dict cu {ticker, sector} din DB — pentru RS și sector heat
    """
    if not tickers:
        print("EROARE: Lista tickers goală")
        return []

    # Mapare ticker → sector din universe
    sector_map: dict[str, str] = {}
    if universe:
        for u in universe:
            t = (u.get("ticker") or "").upper()
            s = u.get("sector") or ""
            if t and s:
                sector_map[t] = s

    print(f"Scan pentru {len(tickers)} tickers...")

    # 1. Download bulk tickers
    raw = yf.download(
        tickers=tickers,
        period="25d",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    # 2. Download ETF-uri sectoriale (o singură dată)
    print("  Calculez Relative Strength vs ETF sectoare...")
    etf_perfs = _download_etf_perfs()

    # 3. Scanează candidații cu vol spike
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
            prev_price = float(hist["Close"].iloc[-2])
            vol_today  = float(hist["Volume"].iloc[-1])

            if price < MIN_PRICE or vol_today == 0:
                continue

            avg_vol = float(hist["Volume"].iloc[:-1].tail(20).mean())
            if avg_vol < 10_000:
                continue

            vol_ratio = vol_today / avg_vol
            if vol_ratio < MIN_VOL_RATIO:
                continue

            perf_ticker = (price / prev_price) - 1
            sector      = sector_map.get(ticker.upper(), "")
            etf_sym     = SECTOR_ETFS.get(sector, "")
            etf_perf    = etf_perfs.get(etf_sym)

            rs_vs_sector = None
            if etf_perf is not None:
                rs_vs_sector = round(perf_ticker - etf_perf, 4)

            candidates.append({
                "ticker":         ticker.upper(),
                "price":          round(price, 2),
                "volume":         int(vol_today),
                "avg_volume_20d": int(avg_vol),
                "vol_ratio":      round(vol_ratio, 2),
                "raw_perf":       round(perf_ticker, 4),
                "sector":         sector,
                "rs_vs_sector":   rs_vs_sector,   # NOU
            })
        except Exception:
            continue

    # 4. Sector Heat Score (arhitectura v2: 5+ companii/sector = "In Play")
    from collections import Counter
    sector_counts = Counter(c["sector"] for c in candidates if c["sector"])

    for c in candidates:
        s = c["sector"]
        heat = sector_counts.get(s, 0)
        c["sector_heat_score"] = heat
        c["sector_in_play"]    = heat >= 5

    # 5. Sort și top N
    candidates.sort(key=lambda x: x["vol_ratio"], reverse=True)
    result = candidates[:TOP_N]

    # Log heat
    hot = [(s, n) for s, n in sector_counts.most_common(5) if n >= 3]
    if hot:
        print(f"  Sectoare calde: {hot}")
    print(f"Găsiți {len(result)} candidați.")
    return result


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_universe, save_scan_results
    universe = get_universe()
    if not universe:
        sys.exit(1)
    tickers_list = [u["ticker"] for u in universe]
    results = run_scan(tickers_list, universe=universe)
    if results:
        save_scan_results(results)
