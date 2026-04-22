"""
Universe builder — rulează o dată pe săptămână (duminică 20:00 UTC).

Strategie:
  Step 1: FMP /stable/stock-list  — 1 call gratuit, aduce toți tickerii
          cu symbol, name, exchange, type
  Step 2: Filtru local pe exchange NYSE/NASDAQ și type=stock
  Step 3: yfinance bulk download — filtrare pe market cap și volum
          Tot gratuit, fără call-uri extra FMP.

FMP calls consumate: 1 (din 250 disponibile)
"""
import os
import sys
import time
import requests
import yfinance as yf
import pandas as pd

FMP_KEY  = os.environ.get("FMP_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/stable"

MARKET_CAP_MIN = 300_000_000       # $300M
MARKET_CAP_MAX = 10_000_000_000    # $10B
AVG_VOLUME_MIN = 200_000
PRICE_MIN      = 5
EXCHANGES      = {"NYSE", "NASDAQ"}
BATCH_SIZE     = 200   # tickers per yfinance download batch


def fetch_stock_list() -> list[str]:
    """
    FMP /stable/stock-list — 1 singur call, gratuit pe free tier.
    Returnează toți tickerii listați cu exchange și type.
    """
    if not FMP_KEY:
        raise ValueError("FMP_KEY nu e setat")

    url = f"{FMP_BASE}/stock-list"
    r   = requests.get(url, params={"apikey": FMP_KEY}, timeout=30)
    r.raise_for_status()
    data = r.json()
    print(f"FMP stock-list: {len(data)} instrumente totale")

    # Filtru rapid local: doar NYSE/NASDAQ, tip stock, fără . în simbol (ADR-uri)
    tickers = [
        item["symbol"] for item in data
        if item.get("exchangeShortName", "").upper() in EXCHANGES
        and item.get("type", "").lower() == "stock"
        and "." not in item.get("symbol", "")
        and len(item.get("symbol", "")) <= 5
    ]
    print(f"Dupa filtru exchange+type: {len(tickers)} tickers")
    return tickers


def filter_by_market_cap(tickers: list[str]) -> list[dict]:
    """
    yfinance bulk download în batches de BATCH_SIZE.
    Filtrare pe market cap, volum, preț — zero API calls FMP.
    """
    universe = []
    total    = len(tickers)
    batches  = [tickers[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

    print(f"yfinance filter: {total} tickers în {len(batches)} batches de {BATCH_SIZE}...")

    for idx, batch in enumerate(batches):
        try:
            # Descarcă ultimele 5 zile pentru preț și volum
            raw = yf.download(
                tickers=batch,
                period="5d",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )

            for ticker in batch:
                try:
                    hist = raw[ticker] if len(batch) > 1 else raw
                    if hist is None or len(hist) < 2:
                        continue
                    hist = hist.dropna(subset=["Close", "Volume"])
                    if len(hist) < 2:
                        continue

                    price      = float(hist["Close"].iloc[-1])
                    avg_volume = float(hist["Volume"].mean())

                    if price < PRICE_MIN or avg_volume < AVG_VOLUME_MIN:
                        continue

                    # market cap via yfinance info (mai lent, doar pt ce trece filtrul de volum)
                    info       = yf.Ticker(ticker).fast_info
                    market_cap = getattr(info, "market_cap", 0) or 0

                    if MARKET_CAP_MIN <= market_cap <= MARKET_CAP_MAX:
                        universe.append({
                            "ticker":       ticker,
                            "company_name": "",   # completat mai jos dacă e nevoie
                            "exchange":     "",
                            "sector":       "",
                            "industry":     "",
                            "market_cap":   int(market_cap),
                            "avg_volume":   int(avg_volume),
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"  Batch {idx+1} eroare: {e}")

        print(f"  Batch {idx+1}/{len(batches)} done | universe: {len(universe)}")
        time.sleep(1)  # pauză între batches

    return universe


def build_universe() -> list[dict]:
    print("=== Universe Builder ===")
    print("Step 1: FMP /stable/stock-list (1 call gratuit)...")
    tickers = fetch_stock_list()

    print(f"\nStep 2: yfinance filter pe {len(tickers)} tickers...")
    universe = filter_by_market_cap(tickers)
    universe.sort(key=lambda x: x["market_cap"], reverse=True)

    print(f"\nUniverse final: {len(universe)} tickers (market cap $300M-$10B)")
    return universe


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import save_universe

    universe = build_universe()
    if not universe:
        print("EROARE: Universe gol")
        sys.exit(1)

    save_universe(universe)
    print(f"Salvat {len(universe)} tickers în Supabase")

    print("\nTop 10:")
    for t in universe[:10]:
        mc = t["market_cap"] / 1e9
        print(f"  {t['ticker']:<8} ${mc:.1f}B  vol={t['avg_volume']:,}")
