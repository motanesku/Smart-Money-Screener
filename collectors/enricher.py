"""
Enricher v4 — restructurare completă a scorului

SCOR NOU (insider scos din scor, rămâne context informativ):
  score_volume:       0-40  vol ratio față de media 20 zile
  score_options:      0-30  options flow (call sweep / put sweep)
  score_short:        0-20  FINRA squeeze setup + short covering
  score_sideways:     0-10  pattern acumulare discretă 21 zile
  ─────────────────────────────────────────────────────────────
  Total max raw:      100 (poate ieși negativ cu penalizări)

DIRECTION (câmp separat, nu afectează scorul):
  BULLISH:      options calls + vol spike + (squeeze setup opțional)
  BEARISH:      options puts + short building + (insider sell opțional)
  DISTRIBUTION: put sweep + short crescător + prețul la maximul 52s
  NEUTRAL:      semnale mixte sau insuficiente

LARGE CAP FIX:
  Pragul scanner vol_ratio >= 2.0 e prea strict pentru large cap.
  Adăugăm filtru alternativ: vol_usd >= 50M$ (price * volume).
  Orice ticker cu spike real în dolari absolut intră, indiferent de ratio.

INSIDER — context pur:
  Nu mai contribuie la scor. Afișat în UI ca informație suplimentară.
  CEO care cumpără 100K$ e irelevant față de un fond care mișcă 300M$.
  Insider sell → note în thesis, nu penalty în scor.
"""

import os
import sys
from datetime import date, datetime, timezone

import yfinance as yf

from app.db import get_client


# ── Profil companie (extins cu date instituționale din yfinance) ──────────────

def get_profile(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        return {
            "name":           info.get("longName") or info.get("shortName") or "",
            "sector":         info.get("sector") or "",
            "industry":       info.get("industry") or "",
            "market_cap":     int(info.get("marketCap") or 0),
            "float_shares":   info.get("floatShares"),
            "pe_ratio":       info.get("trailingPE"),
            "beta":           info.get("beta"),
            # Institutional data — direct din yfinance, fără dependențe noi
            "inst_own_pct":   info.get("heldPercentInstitutions"),  # 0.0-1.0
            "short_float_pct":info.get("shortPercentOfFloat"),       # 0.0-1.0
            "short_ratio_days":info.get("shortRatio"),               # zile acoperire
            # Earnings context
            "earnings_ts":    info.get("earningsTimestamp"),         # Unix timestamp
        }
    except Exception as e:
        print(f"  [yfinance] {ticker} profil eroare: {e}")
        return {}


# ── Persistence count (whale footprint 21 zile) ───────────────────────────────

def get_persistence_count(ticker: str) -> int:
    try:
        from datetime import timedelta
        since = (date.today() - timedelta(days=21)).isoformat()
        res = (
            get_client()
            .table("scan_results")
            .select("scan_date")
            .eq("ticker", ticker.upper())
            .gte("scan_date", since)
            .execute()
        )
        return len({row["scan_date"] for row in (res.data or [])})
    except Exception as e:
        print(f"  [persistence] {ticker} eroare: {e}")
        return 0


# ── Sideways detector (acumulare discretă) ────────────────────────────────────

def get_sideways_score(ticker: str) -> tuple[int, str]:
    """
    Pattern de acumulare: preț sideways (range < 8%) + vol spikes multiple.
    Balenele intră treptat 2-3 săptămâni fără să miște prețul.
    """
    try:
        hist = yf.Ticker(ticker).history(period="21d", interval="1d", auto_adjust=True)
        if len(hist) < 10:
            return 0, "INSUFFICIENT_DATA"

        closes  = hist["Close"].dropna()
        volumes = hist["Volume"].dropna()

        price_range_pct = (closes.max() - closes.min()) / closes.mean()
        avg_vol         = volumes.mean()
        vol_spikes      = int((volumes > avg_vol * 2).sum())

        if price_range_pct < 0.05 and vol_spikes >= 4:
            return 10, "STRONG_ACCUMULATION_PATTERN"
        if price_range_pct < 0.08 and vol_spikes >= 3:
            return 7, "ACCUMULATION_PATTERN"
        if price_range_pct < 0.10 and vol_spikes >= 2:
            return 3, "WEAK_ACCUMULATION"
        return 0, "NO_PATTERN"

    except Exception as e:
        print(f"  [sideways] {ticker} eroare: {e}")
        return 0, "ERROR"


# ── Score helpers ─────────────────────────────────────────────────────────────

def _days_to_earnings(earnings_ts) -> int | None:
    """Câte zile până la următorul earnings. None dacă data nu e disponibilă."""
    if not earnings_ts:
        return None
    try:
        earn_dt = datetime.fromtimestamp(int(earnings_ts), tz=timezone.utc)
        delta   = (earn_dt.date() - date.today()).days
        return delta if delta >= 0 else None  # trecut = ignorăm
    except Exception:
        return None


def _score_volume(vol_ratio: float, vol_usd: float = 0.0) -> tuple[int, str]:
    """
    Scor volum 0-40. Large cap bonus: spike absolut > 50M$ conta chiar
    dacă ratio e sub 2x (NVDA la 1.6x poate fi $4B de volum).
    """
    if vol_ratio >= 5 or vol_usd >= 500_000_000:
        return 40, "EXTREME_SPIKE"
    if vol_ratio >= 3 or vol_usd >= 200_000_000:
        return 30, "HIGH_SPIKE"
    if vol_ratio >= 2 or vol_usd >= 50_000_000:
        return 20, "SPIKE"
    if vol_ratio >= 1.5:
        return 10, "ELEVATED"
    return 5, "ABOVE_AVERAGE"


def _score_short(short: dict, vol_ratio: float = 0.0) -> tuple[int, str]:
    """Scor short flow 0-20 (redus de la 30 pentru a face loc options)."""
    from collectors.finra import score_short
    raw, label = score_short(short, vol_ratio=vol_ratio, insider_buys=0)
    # Remap 0-30 → 0-20
    return int(raw * 2 / 3), label


# ── Direction detector ────────────────────────────────────────────────────────

def _determine_direction(
    opts:    dict,
    short:   dict,
    insider: dict,
    sig_vol: str,
    sig_side:str,
    profile: dict,
) -> str:
    """
    Determină direcția probabilă a mișcării instituționale.
    Nu afectează scorul — e un câmp contextual separat.

    BULLISH:      2+ semnale de acumulare fără semnale de distribuție
    BEARISH:      2+ semnale de distribuție fără semnale de acumulare
    DISTRIBUTION: put sweep + insider selling + prețul la maximul 52s
    NEUTRAL:      semnale mixte sau insuficiente
    """
    opt_dir  = opts.get("options_direction", "NEUTRAL")
    opt_sig  = opts.get("options_signal", "")
    sq_setup = short.get("squeeze_setup", False)
    sh_sig   = short.get("short_signal", "")
    in_sig   = insider.get("net_signal", "NEUTRAL")
    in_10b5  = insider.get("is_10b5_plan", False)

    bullish_signals = sum([
        opt_dir == "BULLISH",
        sq_setup,
        sh_sig == "SHORT_COVERING",
        sig_side in ("STRONG_ACCUMULATION_PATTERN", "ACCUMULATION_PATTERN"),
        sig_vol in ("EXTREME_SPIKE", "HIGH_SPIKE") and opt_dir != "BEARISH",
    ])

    bearish_signals = sum([
        opt_dir == "BEARISH",
        sh_sig in ("HIGH_SHORT_RISK", "EXTREME_SHORT") and not sq_setup,
        in_sig == "DISTRIBUTION" and not in_10b5,
    ])

    # DISTRIBUTION: put sweep clar + prețul la maximul 52s = distribuție clasică
    if opt_sig in ("UNUSUAL_PUT_SWEEP", "UNUSUAL_PUT_BUYING") and in_sig == "DISTRIBUTION":
        return "DISTRIBUTION"

    if bullish_signals >= 2 and bearish_signals == 0:
        return "BULLISH"
    if bullish_signals >= 3:
        return "BULLISH"
    if bearish_signals >= 2 and bullish_signals == 0:
        return "BEARISH"
    if bearish_signals > bullish_signals:
        return "BEARISH"

    return "NEUTRAL"


# ── Haiku AI Analysis ─────────────────────────────────────────────────────────

def get_ai_thesis(enriched_data: dict) -> str:
    """
    Analiză Claude Haiku în română. Rulează doar dacă score >= 55.
    Cunoaște direcția (BULLISH/BEARISH) și o include în analiză.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    score = int(enriched_data.get("score") or 0)
    if score < 55:
        return ""

    try:
        import requests as req

        ticker    = enriched_data.get("ticker", "N/A")
        sector    = enriched_data.get("sector", "N/A")
        direction = enriched_data.get("direction", "NEUTRAL")
        vol_ratio = enriched_data.get("vol_ratio", 0)
        persist   = enriched_data.get("persistence_days_calc", 0)
        opt_sig   = enriched_data.get("options_signal", "N/A")
        pc_ratio  = enriched_data.get("pc_ratio")
        sh_sig    = enriched_data.get("short_signal", "N/A")
        short_r   = enriched_data.get("short_sale_ratio")
        squeeze   = enriched_data.get("squeeze_setup", False)
        in_buys   = enriched_data.get("insider_buys_90d", 0)
        in_sells  = enriched_data.get("insider_sells_90d", 0)
        in_sig    = enriched_data.get("net_insider_signal", "N/A")
        in_role   = enriched_data.get("top_insider_role", "N/A")
        inst_own  = enriched_data.get("inst_own_pct")
        thesis    = enriched_data.get("thesis", "N/A")

        pc_str    = f"{pc_ratio:.2f}" if pc_ratio else "N/A"
        short_str = f"{short_r:.1%}" if short_r else "N/A"
        inst_str  = f"{inst_own:.1%}" if inst_own else "N/A"

        prompt = f"""Ești un analist senior cu 20 ani experiență în urmărirea fluxurilor Smart Money.
Analizează datele și oferă o opinie CONCISĂ în română, maxim 130 cuvinte.

=== {ticker} | Sector: {sector} | Score: {score}/100 ===
DIRECȚIE DETECTATĂ: {direction}

VOLUME: {vol_ratio:.1f}x față de medie | Persistență: {persist} zile din 21
OPTIONS FLOW: {opt_sig} | Put/Call Ratio: {pc_str}
SHORT: Ratio={short_str} | Signal={sh_sig} | Squeeze Setup={squeeze}
INSIDER (context): {in_buys} cumpărări / {in_sells} vânzări | Net={in_sig} | Rol={in_role}
INSTITUȚIONAL: Ownership={inst_str}
Thesis sistem: {thesis}

Răspunde STRICT în format:
VERDICT: [ACUMULARE / DISTRIBUȚIE / FALS SEMNAL / INCERT]
RAȚIONAMENT: [2-3 propoziții — cel mai important argument]
INVALIDARE: [ce ar anula semnalul]
ÎNCREDERE: [RIDICATĂ / MEDIE / SCĂZUTĂ]"""

        response = req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 380,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        text = response.json().get("content", [{}])[0].get("text", "").strip()
        print(f"  [Haiku] {ticker} analiză generată ({len(text)} chars)")
        return text

    except Exception as e:
        print(f"  [Haiku] {ticker} eroare: {e}")
        return ""


# ── Core enrich ───────────────────────────────────────────────────────────────

def enrich_single(ticker: str, scan_data: dict | None = None) -> dict:
    ticker = ticker.upper()
    print(f"  Enriching {ticker}...")

    sd = scan_data or {}

    profile   = get_profile(ticker)
    p_count   = get_persistence_count(ticker)

    from collectors.edgar import get_insider_data_edgar
    insider = get_insider_data_edgar(ticker, days_back=90)

    from collectors.finra import get_short_data
    short = get_short_data(ticker, days_back=5)

    from collectors.options_flow import get_options_flow, score_options
    opts = get_options_flow(ticker)

    s_sideways, sig_side = get_sideways_score(ticker)

    # Date din scanner
    vol_ratio    = float(sd.get("vol_ratio") or 0)
    price        = sd.get("price") or 0.0
    volume       = int(sd.get("volume") or 0)
    avg_vol_20d  = int(sd.get("avg_volume_20d") or 0)
    rs_vs_sector = sd.get("rs_vs_sector")
    sector_heat  = int(sd.get("sector_heat_score") or 0)

    vol_usd = float(price) * volume if price and volume else 0.0

    # ── Scoruri (insider scos) ─────────────────────────────────────────────
    days_to_earn = _days_to_earnings(profile.get("earnings_ts"))

    s_vol,     sig_vol   = _score_volume(vol_ratio, vol_usd)
    s_options, sig_opts  = score_options(opts)
    s_short,   sig_short = _score_short(short, vol_ratio)

    # Bonus earnings proximity: options flow neobișnuit cu <10 zile înainte
    # de earnings e mult mai semnificativ (asimetrie informațională)
    if days_to_earn is not None and 1 <= days_to_earn <= 10 and s_options >= 20:
        s_options = min(s_options + 8, 30)
        sig_opts  = f"{sig_opts}+EARNINGS_PROXIMITY"

    raw_score   = s_vol + s_options + s_short + s_sideways
    total_score = max(0, min(raw_score, 100))

    # ── Direcție ──────────────────────────────────────────────────────────
    direction = _determine_direction(opts, short, insider, sig_vol, sig_side, profile)

    # ── Thesis text ───────────────────────────────────────────────────────
    thesis_parts = []

    if sig_vol in ("EXTREME_SPIKE", "HIGH_SPIKE"):
        usd_str = f"${vol_usd/1e6:.0f}M" if vol_usd >= 1e6 else ""
        thesis_parts.append(f"Vol {vol_ratio:.1f}x {usd_str}".strip())
    if p_count >= 3:
        thesis_parts.append(f"Persistent {p_count}d/21d")
    if days_to_earn is not None and days_to_earn <= 10:
        thesis_parts.append(f"⚡ Earnings în {days_to_earn}z")
    if opts.get("options_signal") in ("UNUSUAL_CALL_SWEEP", "UNUSUAL_CALL_BUYING"):
        pc = opts.get("pc_ratio")
        pc_str = f" P/C={pc:.2f}" if pc else ""
        earn_note = f" [{days_to_earn}z earnings]" if days_to_earn and days_to_earn <= 10 else ""
        thesis_parts.append(f"Call sweep{pc_str}{earn_note}")
    if opts.get("options_signal") in ("UNUSUAL_PUT_SWEEP", "UNUSUAL_PUT_BUYING"):
        thesis_parts.append(f"Put sweep ⚠️ P/C={opts.get('pc_ratio','?')}")
    if short.get("squeeze_setup"):
        thesis_parts.append("SHORT SQUEEZE SETUP")
    elif sig_short == "SHORT_COVERING":
        thesis_parts.append("Short covering")
    if sig_side in ("STRONG_ACCUMULATION_PATTERN", "ACCUMULATION_PATTERN"):
        thesis_parts.append("Sideways accumulation")
    # Insider ca notă contextuală (nu în scor)
    if insider.get("net_signal") == "ACCUMULATION" and insider.get("buys", 0) >= 2:
        thesis_parts.append(f"[ctx: insider buy ${insider.get('buy_value',0):,.0f}]")
    if insider.get("net_signal") == "DISTRIBUTION" and not insider.get("is_10b5_plan"):
        thesis_parts.append(f"[ctx: insider SELL ${insider.get('sell_value',0):,.0f} ⚠️]")

    thesis = " | ".join(thesis_parts) if thesis_parts else "Volume alert"

    enriched = {
        "ticker":               ticker,
        "enrich_date":          date.today().isoformat(),
        "company_name":         profile.get("name", ""),
        "sector":               profile.get("sector", ""),
        "industry":             profile.get("industry", ""),
        "market_cap":           profile.get("market_cap", 0),
        "float_shares":         profile.get("float_shares"),
        "price":                price,
        "volume":               volume,
        "avg_volume_20d":       avg_vol_20d,
        "vol_ratio":            round(vol_ratio, 4),
        "vol_usd":              round(vol_usd, 0),
        "rs_vs_sector":         rs_vs_sector,
        "sector_heat_score":    sector_heat,

        # Insider — context only (nu în scor)
        "insider_buys_90d":     insider.get("buys", 0),
        "insider_buy_value":    insider.get("buy_value", 0.0),
        "insider_sells_90d":    insider.get("sells", 0),
        "insider_sell_value":   insider.get("sell_value", 0.0),
        "top_insider_role":     insider.get("top_role", ""),
        "net_insider_signal":   insider.get("net_signal", "NEUTRAL"),
        "is_10b5_plan":         insider.get("is_10b5_plan", False),

        # Options flow (NOU)
        "call_volume":          opts.get("call_volume", 0),
        "put_volume":           opts.get("put_volume", 0),
        "pc_ratio":             opts.get("pc_ratio"),
        "call_vol_oi_ratio":    opts.get("call_vol_oi_ratio"),
        "unusual_call_strikes": opts.get("unusual_call_strikes", 0),
        "unusual_put_strikes":  opts.get("unusual_put_strikes", 0),
        "options_signal":       opts.get("options_signal", ""),
        "options_direction":    opts.get("options_direction", "NEUTRAL"),

        # Short — FINRA
        "short_interest_pct":    short.get("short_sale_ratio"),
        "short_sale_volume":     short.get("short_sale_volume", 0),
        "total_volume_reported": short.get("total_volume_reported", volume),
        "short_sale_ratio":      short.get("short_sale_ratio"),
        "avg_short_ratio_5d":    short.get("avg_short_ratio_5d"),
        "squeeze_setup":         short.get("squeeze_setup", False),
        "short_flow_signal":     short.get("short_flow_signal", ""),
        "short_signal":          short.get("short_signal", ""),

        # Institutional (din yfinance profile — fără dependențe noi)
        "inst_own_pct":          profile.get("inst_own_pct"),
        "short_float_pct":       profile.get("short_float_pct"),
        "short_ratio_days":      profile.get("short_ratio_days"),

        # Fundamentals
        "pe_ratio":              profile.get("pe_ratio"),
        "beta":                  profile.get("beta"),

        # Scoruri (structura nouă)
        "score":                 total_score,
        "score_volume":          s_vol,
        "score_options":         s_options,
        "score_short":           s_short,
        "score_sideways":        s_sideways,

        # Direcție și semnale
        "direction":             direction,
        "volume_signal":         sig_vol,
        "options_signal_text":   sig_opts,
        "short_squeeze_signal":  sig_short,
        "sideways_signal":       sig_side,
        "thesis":                thesis,

        # Câmpuri legacy (pentru backward compat cu views/queries vechi)
        "score_insider":         0,
        "score_insider_quality": 0,
        "score_ownership":       0,
        "score_short_interest":  s_short,
        "score_short_flow":      s_sideways,
        "score_fundamental":     0,
        "score_penalty":         0,
        "insider_signal":        insider.get("net_signal", "NEUTRAL"),
        "ownership_form":        "",
        "ownership_holder":      "",
        "ownership_pct":         None,
        "ownership_signal":      "",
        "ownership_signal_text": "",
        "inst_ownership_pct":    profile.get("inst_own_pct"),

        # Earnings context
        "days_to_earnings":    days_to_earn,

        # folosit în get_ai_thesis
        "persistence_days_calc": p_count,
    }

    ai_thesis = get_ai_thesis(enriched)
    if ai_thesis:
        enriched["ai_thesis_ro"] = ai_thesis

    return enriched


# ── Public API ────────────────────────────────────────────────────────────────

def enrich_candidates(candidates: list[dict]) -> list[dict]:
    return [enrich_single(c["ticker"], scan_data=c) for c in candidates if c.get("ticker")]


def enrich_watchlist(tickers: list[str], scan_results: list[dict]) -> list[dict]:
    scan_map = {r["ticker"].upper(): r for r in scan_results if "ticker" in r}
    return [enrich_single(t, scan_data=scan_map.get(t.upper())) for t in tickers]


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.db import get_scan_results, save_enriched
    candidates = get_scan_results(days_back=1)
    if candidates:
        res = enrich_candidates(candidates)
        save_enriched(res)
        print(f"Salvat {len(res)} tickers enriched")
    else:
        print("Niciun candidat de enriched")
