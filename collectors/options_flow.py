"""
Options Flow Analyzer — detectează activitate neobișnuită în opțiuni.

Logica Smart Money:
  Instituțiile nu pot ascunde ordinele de opțiuni. Când cineva cumpără
  10,000 call-uri OTM pe un ticker dormit cu 2 săptămâni înainte de un
  announcement, ăla NU e retail.

Semnale bullish (acumulare):
  - Call volume >> Open Interest pe strike-uri OTM (sweeps)
  - P/C ratio < 0.5 (put/call ratio scăzut = dominanță calls)
  - Call-uri near-term cu IV în creștere (cineva plătește premium)

Semnale bearish (distribuție):
  - Put volume >> OI pe strike-uri ATM/ITM (hedging instituțional)
  - P/C ratio > 2.0 (dominanță puts = protecție sau short bet)
  - Put buying la prețuri de exercitare sub preț curent (downside protection)

Sursa: yfinance (gratuit, fără API key — folosim dependency existentă)
"""

from __future__ import annotations

import yfinance as yf

_DEFAULT = {
    "call_volume":            0,
    "put_volume":             0,
    "pc_ratio":               None,
    "call_vol_oi_ratio":      None,
    "put_vol_oi_ratio":       None,
    "unusual_call_strikes":   0,
    "unusual_put_strikes":    0,
    "options_signal":         "NO_DATA",
    "options_direction":      "NEUTRAL",
}


def get_options_flow(ticker: str) -> dict:
    """
    Analizează opțiunile pentru un ticker și returnează semnale de flux.
    Privim primele 2 expirări (cele mai lichide, cele mai informative).
    """
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return _DEFAULT.copy()

        total_call_vol = 0.0
        total_put_vol  = 0.0
        total_call_oi  = 0.0
        total_put_oi   = 0.0
        unusual_calls  = 0
        unusual_puts   = 0

        # Primele 2 expirări = cel mai mult volum, cel mai relevant
        for exp in expirations[:2]:
            try:
                chain = t.option_chain(exp)
                calls = chain.calls.fillna(0)
                puts  = chain.puts.fillna(0)

                cv = float(calls["volume"].sum())
                pv = float(puts["volume"].sum())
                co = float(calls["openInterest"].sum())
                po = float(puts["openInterest"].sum())

                total_call_vol += cv
                total_put_vol  += pv
                total_call_oi  += co
                total_put_oi   += po

                # Strike-uri cu volum neobișnuit (>2x open interest pe același strike)
                if co > 0:
                    unusual_calls += int((calls["volume"] > calls["openInterest"] * 2).sum())
                if po > 0:
                    unusual_puts  += int((puts["volume"]  > puts["openInterest"]  * 2).sum())

            except Exception:
                continue

        if total_call_vol + total_put_vol == 0:
            return _DEFAULT.copy()

        pc_ratio         = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else None
        call_vol_oi_ratio = round(total_call_vol / total_call_oi, 3) if total_call_oi > 0 else None
        put_vol_oi_ratio  = round(total_put_vol  / total_put_oi,  3) if total_put_oi  > 0 else None

        # ── Determinare semnal ───────────────────────────────────────────────
        signal    = "NEUTRAL"
        direction = "NEUTRAL"

        if pc_ratio is not None and call_vol_oi_ratio is not None:
            # Bullish: puts puțini + calls agresive față de OI
            if pc_ratio < 0.4 and call_vol_oi_ratio > 2.0:
                signal    = "UNUSUAL_CALL_SWEEP"   # cel mai clar semnal bullish
                direction = "BULLISH"
            elif pc_ratio < 0.4 and unusual_calls >= 3:
                signal    = "UNUSUAL_CALL_BUYING"
                direction = "BULLISH"
            elif pc_ratio < 0.6 and call_vol_oi_ratio > 1.5:
                signal    = "CALL_DOMINANT"
                direction = "BULLISH"
            # Bearish: puts agresive față de OI
            elif pc_ratio is not None and put_vol_oi_ratio is not None and pc_ratio > 2.5 and put_vol_oi_ratio > 2.0:
                signal    = "UNUSUAL_PUT_SWEEP"    # hedging agresiv sau short bet
                direction = "BEARISH"
            elif pc_ratio is not None and pc_ratio > 2.0 and unusual_puts >= 3:
                signal    = "UNUSUAL_PUT_BUYING"
                direction = "BEARISH"
            elif pc_ratio is not None and pc_ratio > 1.5:
                signal    = "PUT_DOMINANT"
                direction = "BEARISH"

        result = {
            "call_volume":           int(total_call_vol),
            "put_volume":            int(total_put_vol),
            "pc_ratio":              pc_ratio,
            "call_vol_oi_ratio":     call_vol_oi_ratio,
            "put_vol_oi_ratio":      put_vol_oi_ratio,
            "unusual_call_strikes":  unusual_calls,
            "unusual_put_strikes":   unusual_puts,
            "options_signal":        signal,
            "options_direction":     direction,
        }

        print(
            f"  [Options] {ticker}: calls={int(total_call_vol):,} puts={int(total_put_vol):,} "
            f"P/C={pc_ratio} | {signal}"
        )
        return result

    except Exception as e:
        print(f"  [Options] {ticker} eroare: {e}")
        return _DEFAULT.copy()


def score_options(opts: dict) -> tuple[int, str]:
    """
    Scor options flow 0-30.
    Penalizare negativă pentru put sweep (semnalizează distribuție).
    """
    signal        = opts.get("options_signal", "NO_DATA")
    unusual_calls = opts.get("unusual_call_strikes", 0)
    call_oi_ratio = opts.get("call_vol_oi_ratio") or 0.0

    match signal:
        case "UNUSUAL_CALL_SWEEP":
            return 30, signal
        case "UNUSUAL_CALL_BUYING":
            return 22, signal
        case "CALL_DOMINANT":
            bonus = 5 if unusual_calls >= 3 or call_oi_ratio > 2.0 else 0
            return 12 + bonus, signal
        case "PUT_DOMINANT":
            return 0, signal          # neutru — poate fi hedging normal
        case "UNUSUAL_PUT_BUYING":
            return -10, signal        # distribuție probabilă
        case "UNUSUAL_PUT_SWEEP":
            return -20, signal        # distribuție clară
        case _:
            return 0, "NEUTRAL_OPTIONS"


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"\nOptions Flow pentru {ticker}:")
    data = get_options_flow(ticker)
    for k, v in data.items():
        print(f"  {k}: {v}")
    sc, lbl = score_options(data)
    print(f"\nOptions Score: {sc} | {lbl}")
