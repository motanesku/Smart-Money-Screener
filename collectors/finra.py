"""
FINRA Short Sale collector v1 — implementare completă

Sursă: FINRA Daily Short Sale Volume Files (100% gratuit, public)
URL:   https://www.finra.org/investors/learn-to-invest/advanced-investing/short-selling/

Logică Smart Money:
  - Short ratio ridicat + vol spike + insider buying = setup SHORT SQUEEZE
  - Short ratio ridicat + vol spike + insider selling = confirmare DISTRIBUȚIE
  - Short ratio scăzut brusc = short covering (potențial bottom)

Date disponibile:
  - FINRA publică zilnic pentru: NYSE, NASDAQ, OTC, NMS
  - Format CSV: Date, Symbol, ShortVolume, ShortExemptVolume, TotalVolume, Market
  - Fișierele sunt disponibile cu 1 zi întârziere

ATENȚIE — distincție importantă de metrici:
  - short_sale_ratio (FINRA): ShortVolume / TotalVolume pe zi de tranzacționare
    = fracția din volumul zilnic care e vânzare short, NU % din float
    Valori tipice: 0.30-0.55 sunt normale; praguri de mai sus sunt calibrate pentru asta.
  - short_float_pct (yfinance): ShortInterest / FloatShares
    = % din acțiunile disponibile care sunt vândute short (ex. GME era 140%)
    Survine din raportările bi-lunare FINRA/exchanges, latență 2 săptămâni.
  Cele două NU sunt comparabile direct. Pragurile din această funcție se referă la
  short_sale_ratio FINRA zilnic, nu la short % of float.
"""

import io
import time
from datetime import date, timedelta

import pandas as pd
import requests

HEADERS = {"User-Agent": "SmartMoneyScreener research@screener.com"}

# FINRA publică date pentru mai multe piețe; NMS e cel mai complet
FINRA_URLS = {
    "NMS": "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt",
    "NYSE": "https://cdn.finra.org/equity/regsho/daily/CNYSEshvol{date}.txt",
}

_CACHE: dict[str, pd.DataFrame] = {}


def _get_trading_day(offset: int = 0) -> str:
    """
    Returnează ultima zi de tranzacționare (sărim weekendul).
    offset=0 → ieri (FINRA publică cu 1 zi întârziere)
    offset=1 → alaltăieri (pentru siguranță dacă fișierul nu e încă disponibil)
    """
    d = date.today() - timedelta(days=1 + offset)
    # Sărim weekendul
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _download_finra_file(market: str = "NMS", date_str: str | None = None) -> pd.DataFrame | None:
    """
    Descarcă și parsează fișierul CSV FINRA pentru o zi.
    Returnează DataFrame cu coloane: Symbol, ShortVolume, TotalVolume, ShortRatio
    """
    cache_key = f"{market}_{date_str}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if date_str is None:
        date_str = _get_trading_day(0)

    url = FINRA_URLS.get(market, FINRA_URLS["NMS"]).format(date=date_str)

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 404:
            # Fișierul nu e încă disponibil — încearcă ziua precedentă
            date_str = _get_trading_day(1)
            url = FINRA_URLS[market].format(date=date_str)
            r = requests.get(url, headers=HEADERS, timeout=30)

        r.raise_for_status()

        df = pd.read_csv(
            io.StringIO(r.text),
            sep="|",
            dtype={"Symbol": str, "ShortVolume": float, "TotalVolume": float},
        )

        # Curățăm și calculăm ratio
        df = df.dropna(subset=["Symbol", "ShortVolume", "TotalVolume"])
        df = df[df["TotalVolume"] > 0]
        df["ShortRatio"] = (df["ShortVolume"] / df["TotalVolume"]).round(4)
        df["Symbol"] = df["Symbol"].str.upper().str.strip()

        _CACHE[cache_key] = df
        print(f"  [FINRA] Descărcat {market} {date_str}: {len(df):,} simboluri")
        return df

    except Exception as e:
        print(f"  [FINRA] Eroare download {market} {date_str}: {e}")
        return None


def get_short_data(ticker: str, days_back: int = 5) -> dict:
    """
    Returnează datele de short selling pentru un ticker.

    Returns:
        short_sale_volume     — volum short azi
        total_volume_reported — volum total FINRA azi
        short_sale_ratio      — short/total (0.0 - 1.0)
        short_flow_signal     — "HIGH_SHORT" / "ELEVATED_SHORT" / "NORMAL" / "LOW_SHORT"
        short_signal          — semnal compus pentru scoring
        avg_short_ratio_5d    — media pe 5 zile (pentru trend)
        short_ratio_change    — schimbare față de medie (covering sau creștere)
        squeeze_setup         — True dacă setup pentru short squeeze
    """
    default = {
        "short_sale_volume":     0,
        "total_volume_reported": 0,
        "short_sale_ratio":      None,
        "short_flow_signal":     "UNKNOWN",
        "short_signal":          "NO_DATA",
        "avg_short_ratio_5d":    None,
        "short_ratio_change":    None,
        "squeeze_setup":         False,
    }

    # Colectăm date pe mai multe zile pentru trend
    ratios = []
    latest = None

    for offset in range(days_back):
        date_str = _get_trading_day(offset)
        df = _download_finra_file("NMS", date_str)
        if df is None:
            continue

        row = df[df["Symbol"] == ticker.upper()]
        if row.empty:
            # Încearcă NYSE dacă nu e în NMS
            df2 = _download_finra_file("NYSE", date_str)
            if df2 is not None:
                row = df2[df2["Symbol"] == ticker.upper()]

        if not row.empty:
            r = row.iloc[0]
            ratio = float(r["ShortRatio"])
            ratios.append(ratio)
            if latest is None:
                latest = {
                    "short_sale_volume":     int(r["ShortVolume"]),
                    "total_volume_reported": int(r["TotalVolume"]),
                    "short_sale_ratio":      ratio,
                }

        time.sleep(0.05)  # rate limiting

    if latest is None:
        return default

    avg_ratio = sum(ratios) / len(ratios) if ratios else None
    ratio_change = None
    if avg_ratio and len(ratios) >= 2:
        ratio_change = round(ratios[0] - (sum(ratios[1:]) / len(ratios[1:])), 4)

    sr = latest["short_sale_ratio"]

    # Semnal flux short
    if sr >= 0.50:
        flow_signal = "EXTREME_SHORT"
    elif sr >= 0.40:
        flow_signal = "HIGH_SHORT"
    elif sr >= 0.30:
        flow_signal = "ELEVATED_SHORT"
    elif sr >= 0.20:
        flow_signal = "NORMAL"
    else:
        flow_signal = "LOW_SHORT"

    # Short covering: ratio scade brusc față de medie = potențial bottom
    covering = ratio_change is not None and ratio_change < -0.05

    # Setup squeeze: short ratio ridicat + covering activ
    squeeze_setup = sr >= 0.35 and covering

    # Semnal compus
    if squeeze_setup:
        short_signal = "SQUEEZE_SETUP"
    elif flow_signal in ("EXTREME_SHORT", "HIGH_SHORT"):
        short_signal = "HIGH_SHORT_RISK"
    elif covering and sr >= 0.25:
        short_signal = "SHORT_COVERING"
    else:
        short_signal = flow_signal

    result = {
        **latest,
        "short_flow_signal":  flow_signal,
        "short_signal":       short_signal,
        "avg_short_ratio_5d": round(avg_ratio, 4) if avg_ratio else None,
        "short_ratio_change": ratio_change,
        "squeeze_setup":      squeeze_setup,
    }
    print(
        f"  [FINRA] {ticker}: ratio={sr:.1%} | signal={short_signal} "
        f"| covering={covering}"
    )
    return result


def score_short(short_data: dict, vol_ratio: float = 0.0, insider_buys: int = 0) -> tuple[int, str]:
    """
    Calculează scorul short (0-30) pe baza datelor FINRA.

    Logică:
    - Short squeeze setup (short ridicat + covering + vol spike + insider buy) = max 30
    - High short fără covering = risc, nu semnal pozitiv → scor neutral sau penalty
    - Covering singur = semnal pozitiv moderat

    Returns: (scor 0-30, descriere semnal)
    """
    sr    = short_data.get("short_sale_ratio") or 0.0
    sig   = short_data.get("short_signal", "NO_DATA")
    cover = short_data.get("short_ratio_change") or 0.0

    if sig == "SQUEEZE_SETUP" and vol_ratio >= 2.0 and insider_buys >= 1:
        return 30, "PERFECT_SQUEEZE_SETUP"
    if sig == "SQUEEZE_SETUP" and vol_ratio >= 2.0:
        return 22, "SQUEEZE_SETUP"
    if sig == "SHORT_COVERING" and vol_ratio >= 2.0:
        return 18, "COVERING_WITH_VOLUME"
    if sig == "HIGH_SHORT_RISK" and insider_buys >= 2:
        # Insider buying în ciuda short-ului ridicat = convingere
        return 15, "INSIDER_VS_SHORT"
    if sr >= 0.30 and cover < -0.03:
        return 12, "SHORT_COVERING"
    if sr >= 0.40:
        # Short ridicat fără covering = risc, scor neutru
        return 0, "HIGH_SHORT_NO_SIGNAL"

    return 0, "NORMAL_SHORT"


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "GME"
    print(f"\nTest FINRA Short Data pentru {ticker}:")
    data = get_short_data(ticker, days_back=3)
    for k, v in data.items():
        print(f"  {k}: {v}")
    score, label = score_short(data, vol_ratio=3.0, insider_buys=1)
    print(f"\nShort Score: {score} | {label}")
