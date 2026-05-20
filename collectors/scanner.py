"""
Scanner v2 — Witness-Based Smart Money Detection

Înlocuiește atât scanner.py cât și enricher.py din v1.
Sursa de date: exclusiv yfinance (daily OHLCV). Zero API-uri externe.

Martori calculați pentru fiecare ticker:
  vol_zscore_21v63  — deviații standard ale mediei 21d față de baseline 63d
  vol_witness       — CERERE / OFERTĂ / AMBIGUU / NEUTRU (calificare direcțională)
  atr_pct_63d       — percentila ATR în ultimele 63 de zile (0=compresie maximă)
  range_width_21d   — lățimea % a range-ului pe 21 de zile
  rs_defense_score  — cât de bine rezistă acțiunea față de sector în zilele DOWN
  wyckoff_witness   — SPRING / PHASE_B / DISTRIBUTION / NONE
  poc_1y / poc_3m   — Point of Control 1 an și 3 luni (volum profile din OHLCV)
  trend_label       — eticheta finală derivată din convergența martorilor

Rulează zilnic EOD (după închiderea pieței).
"""
import sys
import time
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

SECTOR_ETFS: dict[str, str] = {
    "Technology":             "XLK",
    "Healthcare":             "XLV",
    "Health Care":            "XLV",
    "Financials":             "XLF",
    "Financial Services":     "XLF",
    "Energy":                 "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Cyclical":      "XLY",
    "Consumer Staples":       "XLP",
    "Consumer Defensive":     "XLP",
    "Industrials":            "XLI",
    "Basic Materials":        "XLB",
    "Materials":              "XLB",
    "Real Estate":            "XLRE",
    "Utilities":              "XLU",
    "Communication Services": "XLC",
}

TREND_ORDER = [
    "GATA DE BREAKOUT",
    "ACUMULARE ASCUNSĂ",
    "DISTRIBUȚIE",
    "EPUIZARE",
    "CONSOLIDARE NEUTRĂ",
    "FĂRĂ SEMNAL",
]


# ── Helpers de calcul ─────────────────────────────────────────

def _safe_float(x) -> float | None:
    try:
        v = float(x)
        return None if np.isnan(v) or np.isinf(v) else v
    except Exception:
        return None


def calculate_vol_zscore(hist: pd.DataFrame,
                          short_w: int = 21,
                          long_w: int = 63) -> float | None:
    """
    Z-score: câte σ este media de volum pe 21d față de baseline-ul 63d.
    Pozitiv = volum crescut recent. Negativ = volum secat.
    """
    vol = hist["Volume"].dropna()
    if len(vol) < long_w:
        return None
    recent_mean  = float(vol.tail(short_w).mean())
    baseline     = vol.tail(long_w)
    base_mean    = float(baseline.mean())
    base_std     = float(baseline.std())
    if base_std < 1:
        return None
    return round((recent_mean - base_mean) / base_std, 3)


def calculate_vol_witness(hist: pd.DataFrame,
                           vol_zscore: float | None) -> tuple[str, float]:
    """
    Califică direcția volumului pe baza poziției close-ului în range-ul zilei.
    Returnează (witness: str, close_position: float 0-1).
    """
    row    = hist.iloc[-1]
    spread = _safe_float(row["High"] - row["Low"]) or 0.0

    if spread < 1e-6:
        close_pos = 0.5
    else:
        close_pos = float((row["Close"] - row["Low"]) / spread)
        close_pos = max(0.0, min(1.0, close_pos))

    if vol_zscore is not None and vol_zscore > 1.5:
        if close_pos > 0.66:
            witness = "CERERE"
        elif close_pos < 0.33:
            witness = "OFERTĂ"
        else:
            witness = "AMBIGUU"
    else:
        witness = "NEUTRU"

    return witness, round(close_pos, 3)


def calculate_atr_percentile(hist: pd.DataFrame,
                               atr_period: int = 14,
                               window: int = 63) -> tuple[float | None, float | None]:
    """
    Returnează (atr_14, atr_pct_63d).
    atr_pct_63d = percentila 0-100; sub 15 = compresie extremă.
    """
    df = hist.dropna(subset=["High", "Low", "Close"])
    if len(df) < atr_period + window:
        return None, None

    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"]  - df["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)

    atr_series = tr.rolling(atr_period).mean().dropna()
    if len(atr_series) < window:
        return None, None

    current_atr = float(atr_series.iloc[-1])
    historical  = atr_series.tail(window)
    pct         = float((historical < current_atr).sum() / len(historical) * 100)

    return round(current_atr, 6), round(pct, 1)


def calculate_range_width(hist: pd.DataFrame, window: int = 21) -> float | None:
    """Lățimea % a range-ului (High-Low) pe ultimele N zile față de Low."""
    recent = hist.tail(window)
    low    = _safe_float(recent["Low"].min())
    high   = _safe_float(recent["High"].max())
    if not low or not high or low <= 0:
        return None
    return round((high - low) / low * 100, 3)


def calculate_rs_defense(hist: pd.DataFrame,
                           etf_closes: pd.DataFrame,
                           sector: str,
                           window: int = 21) -> tuple[float | None, int]:
    """
    Câte % din zilele DOWN ale sectorului acțiunea a rezistat (scăzut <0.2%).
    Returnează (rs_defense_score 0-1, rs_defense_days).
    """
    etf = SECTOR_ETFS.get(sector, "")
    if not etf or etf not in etf_closes.columns:
        return None, 0

    stock_ret = hist["Close"].pct_change()
    etf_ret   = etf_closes[etf].pct_change()

    aligned = pd.DataFrame({"stock": stock_ret, "sector": etf_ret}).dropna().tail(window)
    if len(aligned) < 5:
        return None, 0

    down_days = aligned[aligned["sector"] < -0.005]
    if len(down_days) == 0:
        return 0.5, 0

    defense_days  = int((down_days["stock"] > -0.002).sum())
    defense_score = round(defense_days / len(down_days), 3)
    return defense_score, defense_days


def detect_spring(hist: pd.DataFrame, range_window: int = 21) -> tuple[bool, str | None]:
    """
    Spring Wyckoff: prețul iese scurt sub suportul range-ului pe volum MIC,
    apoi închide înapoi în range.
    Volumul mic este esențial — dacă era mare, e breakdown real.
    """
    if len(hist) < range_window + 3:
        return False, None

    support    = float(hist.tail(range_window + 5).iloc[:range_window]["Low"].min())
    vol_avg_20 = float(hist.tail(20)["Volume"].mean())
    if vol_avg_20 <= 0:
        return False, None

    for i in range(-3, 0):
        row   = hist.iloc[i]
        low   = _safe_float(row["Low"]) or 0.0
        close = _safe_float(row["Close"]) or 0.0
        vol   = _safe_float(row["Volume"]) or 0.0

        if (low < support * 0.995 and
                close > support and
                vol < vol_avg_20 * 0.75):
            idx = hist.index[i]
            spring_date = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
            return True, spring_date

    return False, None


def detect_wyckoff_phase(hist: pd.DataFrame,
                          atr_pct: float | None,
                          vol_zscore: float | None,
                          range_width: float | None) -> str:
    """
    Detectează faza Wyckoff pe baza martorilor disponibili.
    SPRING detectat separat (înainte de apelul acestei funcții).
    """
    if atr_pct is None or vol_zscore is None:
        return "NONE"

    recent = hist.tail(5)
    upper_wick_days = 0
    for _, row in recent.iterrows():
        spread = _safe_float(row["High"] - row["Low"]) or 0.0
        if spread < 1e-6:
            continue
        close_pos = float((row["Close"] - row["Low"]) / spread)
        if close_pos < 0.40:
            upper_wick_days += 1

    if vol_zscore > 1.0 and upper_wick_days >= 3 and atr_pct > 50:
        return "DISTRIBUTION"

    if range_width is not None and range_width < 8 and vol_zscore > 0.3:
        return "PHASE_B"

    return "NONE"


def calculate_poc(hist: pd.DataFrame,
                   period_days: int,
                   n_buckets: int = 100) -> tuple[float | None, float | None, float | None]:
    """
    Aproximare Volume Profile din OHLCV zilnic.
    Distribuie volumul fiecărei zile uniform pe range-ul High-Low al acelei zile.
    Returnează (poc_price, vah_price, val_price).
    vah/val = Value Area (70% din volum).
    """
    df = hist.tail(period_days).dropna(subset=["High", "Low", "Volume"])
    if len(df) < 10:
        return None, None, None

    price_min = float(df["Low"].min())
    price_max = float(df["High"].max())
    if price_max <= price_min:
        p = float(df["Close"].iloc[-1])
        return p, p, p

    bucket_size  = (price_max - price_min) / n_buckets
    vol_buckets  = np.zeros(n_buckets)

    for _, row in df.iterrows():
        low  = float(row["Low"])
        high = float(row["High"])
        vol  = float(row["Volume"])
        if vol <= 0 or np.isnan(low) or np.isnan(high):
            continue

        first_b = max(0,           int((low  - price_min) / bucket_size))
        last_b  = min(n_buckets-1, int((high - price_min) / bucket_size))
        n_active = last_b - first_b + 1
        vol_buckets[first_b: last_b + 1] += vol / n_active

    poc_bucket = int(np.argmax(vol_buckets))
    poc_price  = price_min + (poc_bucket + 0.5) * bucket_size

    # Value Area — 70% din volum pornind de la POC în exterior
    total_vol   = vol_buckets.sum()
    if total_vol == 0:
        return round(poc_price, 4), None, None

    target_vol   = total_vol * 0.70
    sorted_idx   = np.argsort(vol_buckets)[::-1]
    cumulative   = 0.0
    va_set: set[int] = set()
    for b in sorted_idx:
        cumulative += vol_buckets[b]
        va_set.add(int(b))
        if cumulative >= target_vol:
            break

    vah = price_min + (max(va_set) + 1) * bucket_size
    val = price_min + min(va_set) * bucket_size

    return round(poc_price, 4), round(vah, 4), round(val, 4)


def derive_trend_label(atr_pct: float | None,
                        vol_zscore: float | None,
                        vol_witness: str,
                        rs_defense: float | None,
                        wyckoff: str,
                        dist_poc_1y: float | None,
                        range_width: float | None) -> str:
    """
    Derivă eticheta finală din convergența martorilor.
    Ordinea regulilor = prioritate.
    """
    rs   = rs_defense or 0.0
    dist = dist_poc_1y or 0.0
    rng  = range_width or 999.0
    atr  = atr_pct or 50.0
    zs   = vol_zscore or 0.0

    # 1. Spring confirmat + forță relativă → gata de ieșire din range
    if wyckoff == "SPRING" and rs > 0.40:
        return "GATA DE BREAKOUT"

    # 2. ATR comprimat + cerere volumetrică + rezistență + lateral
    if (atr < 20 and
            vol_witness in ("CERERE", "AMBIGUU") and
            rs > 0.35 and
            rng < 8):
        return "ACUMULARE ASCUNSĂ"

    # 3. Ofertă pe volum + prețul sus față de POC + sector slab
    if (vol_witness == "OFERTĂ" and
            rs < 0.30 and
            dist > 25):
        return "DISTRIBUȚIE"

    # 4. Volatilitate explodată + ofertă → exhaustion
    if atr > 70 and vol_witness == "OFERTĂ":
        return "EPUIZARE"

    # 5. Lateral fără semnal directional clar
    if atr < 30 and vol_witness == "NEUTRU" and rng < 10:
        return "CONSOLIDARE NEUTRĂ"

    return "FĂRĂ SEMNAL"


# ── Analiză per ticker ────────────────────────────────────────

def analyze_ticker(ticker: str,
                    hist: pd.DataFrame,
                    etf_closes: pd.DataFrame,
                    sector: str,
                    company_name: str,
                    market_cap: int) -> dict | None:
    """Calculează toți martorii pentru un singur ticker."""
    try:
        hist = hist.dropna(subset=["Close", "High", "Low", "Volume"])
        if len(hist) < 65:
            return None

        price      = _safe_float(hist["Close"].iloc[-1])
        prev_price = _safe_float(hist["Close"].iloc[-2])
        if not price or price < 1.0:
            return None

        price_chg = round((price - prev_price) / prev_price * 100, 4) if prev_price else 0.0
        vol_today  = int(hist["Volume"].iloc[-1])
        vol_20d    = int(hist["Volume"].tail(21).iloc[:-1].mean())
        vol_63d    = int(hist["Volume"].tail(64).iloc[:-1].mean())
        high_52w   = _safe_float(hist.tail(252)["High"].max())
        low_52w    = _safe_float(hist.tail(252)["Low"].min())

        # ── Martori ──────────────────────────────────────────
        vol_zscore             = calculate_vol_zscore(hist)
        vol_witness, close_pos = calculate_vol_witness(hist, vol_zscore)
        atr_14, atr_pct        = calculate_atr_percentile(hist)
        range_width            = calculate_range_width(hist)
        rs_score, rs_days      = calculate_rs_defense(hist, etf_closes, sector)

        spring_ok, spring_date = detect_spring(hist)
        wyckoff = "SPRING" if spring_ok else detect_wyckoff_phase(hist, atr_pct, vol_zscore, range_width)

        poc_1y, vah_1y, val_1y = calculate_poc(hist, period_days=252)
        poc_3m, _,      _      = calculate_poc(hist, period_days=63)

        dist_1y = round((price - poc_1y) / poc_1y * 100, 3) if poc_1y else None
        dist_3m = round((price - poc_3m) / poc_3m * 100, 3) if poc_3m else None

        trend_label = derive_trend_label(
            atr_pct, vol_zscore, vol_witness, rs_score,
            wyckoff, dist_1y, range_width
        )

        return {
            "ticker":           ticker,
            "company_name":     company_name,
            "sector":           sector,
            "market_cap":       market_cap,
            "price":            round(price, 4),
            "price_change_pct": price_chg,
            "high_52w":         high_52w,
            "low_52w":          low_52w,
            "vol_today":        vol_today,
            "vol_avg_20d":      vol_20d,
            "vol_avg_63d":      vol_63d,
            "vol_zscore_21v63": vol_zscore,
            "vol_witness":      vol_witness,
            "close_position":   close_pos,
            "atr_14":           atr_14,
            "atr_pct_63d":      atr_pct,
            "range_width_21d":  range_width,
            "rs_defense_score": rs_score,
            "rs_defense_days":  rs_days,
            "sector_etf":       SECTOR_ETFS.get(sector, ""),
            "wyckoff_witness":  wyckoff,
            "spring_date":      spring_date,
            "poc_1y":           poc_1y,
            "vah_1y":           vah_1y,
            "val_1y":           val_1y,
            "poc_3m":           poc_3m,
            "dist_poc_1y_pct":  dist_1y,
            "dist_poc_3m_pct":  dist_3m,
            "trend_label":      trend_label,
        }
    except Exception as e:
        print(f"  [analyze] {ticker}: {e}")
        return None


# ── Scan principal ────────────────────────────────────────────

def run_scan() -> list[dict]:
    """
    Scanează întreg universul zilnic EOD.
    Descarcă 1 an de date OHLCV per ticker (batch-uri de 50).
    Salvează TOȚI tickerii analizați în enriched_v2 (filtrul e în UI).
    Returnează doar cei cu semnal activ (trend_label != FĂRĂ SEMNAL).
    """
    sys.path.insert(0, ".")
    from app.db import get_universe, save_enriched_v2

    universe = get_universe()
    if not universe:
        print("EROARE: Universe gol. Rulează universe mai întâi.")
        return []

    tickers      = [u["ticker"]      for u in universe]
    sector_map   = {u["ticker"]: u.get("sector", "")       for u in universe}
    name_map     = {u["ticker"]: u.get("company_name", "")  for u in universe}
    cap_map      = {u["ticker"]: int(u.get("market_cap", 0)) for u in universe}

    print(f"=== Scanner v2 | {date.today()} ===")
    print(f"Universe: {len(tickers)} tickers")

    # Descarcă toate ETF-urile sectoriale (1 an)
    etf_symbols = list(set(SECTOR_ETFS.values()))
    print(f"Descarc {len(etf_symbols)} sector ETFs...")
    try:
        etf_raw = yf.download(
            etf_symbols,
            period="1y",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        # yfinance multi-ticker → MultiIndex (field, ticker) sau (ticker, field)
        if hasattr(etf_raw.columns, "levels"):
            try:
                etf_closes = etf_raw["Close"]
            except KeyError:
                etf_closes = etf_raw.xs("Close", axis=1, level=1)
        else:
            etf_closes = etf_raw[["Close"]].rename(columns={"Close": etf_symbols[0]})
    except Exception as e:
        print(f"  ETF download eroare: {e}")
        etf_closes = pd.DataFrame()

    # Batch download tickers
    BATCH = 50
    all_results: list[dict] = []
    total_batches = (len(tickers) + BATCH - 1) // BATCH

    for i in range(0, len(tickers), BATCH):
        batch   = tickers[i: i + BATCH]
        batch_n = i // BATCH + 1
        print(f"  Batch {batch_n}/{total_batches}: {len(batch)} tickers")

        try:
            raw = yf.download(
                batch,
                period="1y",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
        except Exception as e:
            print(f"  Batch {batch_n} download eroare: {e}")
            continue

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

                hist = hist.dropna(how="all")
                result = analyze_ticker(
                    ticker,
                    hist,
                    etf_closes,
                    sector_map.get(ticker, ""),
                    name_map.get(ticker, ""),
                    cap_map.get(ticker, 0),
                )
                if result:
                    all_results.append(result)
            except Exception as e:
                print(f"  {ticker}: {e}")

        if i + BATCH < len(tickers):
            time.sleep(0.5)

    # Salvează tot în DB (filtrul e în Streamlit UI)
    save_enriched_v2(all_results)

    # Returnează doar cei cu semnal activ, sortați după prioritate
    signals = [r for r in all_results if r["trend_label"] != "FĂRĂ SEMNAL"]
    signals.sort(key=lambda x: TREND_ORDER.index(x.get("trend_label", "FĂRĂ SEMNAL"))
                 if x.get("trend_label") in TREND_ORDER else 99)

    # Rezumat
    from collections import Counter
    label_counts = Counter(r["trend_label"] for r in all_results)
    print(f"\nRezumat scan:")
    for label in TREND_ORDER:
        n = label_counts.get(label, 0)
        if n:
            print(f"  {label:<25} {n}")
    print(f"Total analizați: {len(all_results)} | Cu semnal: {len(signals)}")

    return signals


if __name__ == "__main__":
    results = run_scan()
    if results:
        print("\nTop semnale:")
        for r in results[:10]:
            print(f"  {r['ticker']:<8} {r['trend_label']:<25} "
                  f"ATR%={r.get('atr_pct_63d', '-'):<6} "
                  f"vol_z={r.get('vol_zscore_21v63', '-'):<7} "
                  f"rs={r.get('rs_defense_score', '-')}")
