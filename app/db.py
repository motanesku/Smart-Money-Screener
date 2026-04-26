"""
DB v10 — fixes:
- score_insider NU mai e hardcodat 0 (Bug critic v9)
- score_insider_quality NU mai e hardcodat 0
- score_fundamental salvat corect
- sector_heat_score coloană nouă (pentru Sector Heat Score din scanner)
- get_sector_stats() pentru heatmap Streamlit
"""
import os
from datetime import date, timedelta
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]


def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── UNIVERSE ──────────────────────────────────────────────────────────────────

def save_universe(tickers: list[dict]):
    if not tickers:
        return
    rows = [{
        "ticker":       (t.get("ticker") or "").upper(),
        "company_name": t.get("company_name") or "",
        "exchange":     t.get("exchange") or "",
        "sector":       t.get("sector") or "",
        "industry":     t.get("industry") or "",
        "market_cap":   int(t.get("market_cap") or 0),
        "avg_volume":   int(t.get("avg_volume") or t.get("avg_volume_20d") or 0),
    } for t in tickers]
    get_client().table("universe").upsert(rows, on_conflict="ticker").execute()


def get_universe() -> list[dict]:
    res = get_client().table("universe").select(
        "ticker,company_name,sector,industry,market_cap,avg_volume").execute()
    return res.data or []


# ── SCAN ──────────────────────────────────────────────────────────────────────

def save_scan_results(results: list[dict]):
    if not results:
        return
    today = date.today().isoformat()
    rows = [{
        "scan_date":          today,
        "ticker":             (r.get("ticker") or "").upper(),
        "price":              r.get("price"),
        "volume":             int(r.get("volume") or 0),
        "avg_volume_20d":     int(r.get("avg_volume_20d") or r.get("avg_volume") or 0),
        "vol_ratio":          r.get("vol_ratio"),
        "rs_vs_sector":       r.get("rs_vs_sector"),       # NOU v2
        "sector_heat_score":  r.get("sector_heat_score"),  # NOU v2
    } for r in results]
    get_client().table("scan_results").upsert(rows, on_conflict="scan_date,ticker").execute()


def get_scan_results(days_back: int = 1) -> list[dict]:
    since = (date.today() - timedelta(days=days_back)).isoformat()
    res = (get_client().table("scan_results").select("*")
           .gte("scan_date", since).order("vol_ratio", desc=True).execute())
    return res.data or []


# ── ENRICH ────────────────────────────────────────────────────────────────────

def save_enriched(results: list[dict]):
    if not results:
        return
    today = date.today().isoformat()
    rows = []
    for r in results:
        rows.append({
            "enrich_date":           today,
            "ticker":                (r.get("ticker") or "").upper(),
            # Companie
            "company_name":          r.get("company_name") or "",
            "sector":                r.get("sector") or "",
            "industry":              r.get("industry") or "",
            "market_cap":            int(r.get("market_cap") or 0),
            # Volume
            "price":                 r.get("price"),
            "volume":                int(r.get("volume") or 0),
            "avg_volume_20d":        int(r.get("avg_volume_20d") or r.get("avg_volume") or 0),
            "vol_ratio":             r.get("vol_ratio"),
            # Sector context (din scanner)
            "rs_vs_sector":          r.get("rs_vs_sector"),
            "sector_heat_score":     int(r.get("sector_heat_score") or 0),
            # Insider — date reale Form 4
            "insider_buys_90d":      int(r.get("insider_buys_90d") or 0),
            "insider_buy_value":     float(r.get("insider_buy_value") or 0),
            "insider_sells_90d":     int(r.get("insider_sells_90d") or 0),
            "insider_sell_value":    float(r.get("insider_sell_value") or 0),
            "top_insider_role":      r.get("top_insider_role") or "",
            "net_insider_signal":    r.get("net_insider_signal") or "",
            "is_10b5_plan":          bool(r.get("is_10b5_plan", False)),
            # Institutional
            "inst_ownership_pct":    r.get("inst_ownership_pct"),
            # Ownership 13D/13G
            "ownership_form":        r.get("ownership_form") or "",
            "ownership_holder":      r.get("ownership_holder") or "",
            "ownership_pct":         r.get("ownership_pct"),
            "ownership_signal":      r.get("ownership_signal") or "",
            "ownership_signal_text": r.get("ownership_signal_text") or "",
            # Short — date reale FINRA
            "short_interest_pct":    r.get("short_interest_pct"),
            "short_sale_volume":     int(r.get("short_sale_volume") or 0),
            "total_volume_reported": int(r.get("total_volume_reported") or r.get("volume") or 0),
            "short_sale_ratio":      r.get("short_sale_ratio"),
            "avg_short_ratio_5d":    r.get("avg_short_ratio_5d"),
            "squeeze_setup":         bool(r.get("squeeze_setup", False)),
            "short_flow_signal":     r.get("short_flow_signal") or "",
            "short_signal":          r.get("short_signal") or "",
            "short_squeeze_signal":  r.get("short_squeeze_signal") or "",
            # Accumulation pattern
            "sideways_signal":       r.get("sideways_signal") or "",
            # Fundamentals
            "pe_ratio":              r.get("pe_ratio"),
            "beta":                  r.get("beta"),
            # Scoruri
            "score":                 int(r.get("score") or 0),
            "score_volume":          int(r.get("score_volume") or 0),
            "score_insider":         int(r.get("score_insider") or 0),
            "score_insider_quality": int(r.get("score_insider_quality") or 0),
            "score_ownership":       int(r.get("score_ownership") or 0),
            "score_short_interest":  int(r.get("score_short_interest") or 0),
            "score_short_flow":      int(r.get("score_short_flow") or 0),
            "score_fundamental":     int(r.get("score_fundamental") or 0),
            "score_penalty":         int(r.get("score_penalty") or 0),
            # Options flow (NOU v4)
            "call_volume":           int(r.get("call_volume") or 0),
            "put_volume":            int(r.get("put_volume") or 0),
            "pc_ratio":              r.get("pc_ratio"),
            "call_vol_oi_ratio":     r.get("call_vol_oi_ratio"),
            "unusual_call_strikes":  int(r.get("unusual_call_strikes") or 0),
            "unusual_put_strikes":   int(r.get("unusual_put_strikes") or 0),
            "options_signal":        r.get("options_signal") or "",
            "options_direction":     r.get("options_direction") or "",
            "options_signal_text":   r.get("options_signal_text") or "",
            # Direcție (NOU v4)
            "direction":             r.get("direction") or "NEUTRAL",
            # Volume USD (large cap fix)
            "vol_usd":               int(r.get("vol_usd") or 0),
            # Institutional (din yfinance — fără API key nou)
            "inst_own_pct":          r.get("inst_own_pct"),
            "short_float_pct":       r.get("short_float_pct"),
            "short_ratio_days":      r.get("short_ratio_days"),
            "float_shares":          int(r.get("float_shares") or 0) if r.get("float_shares") else None,
            # Scoruri noi (v4 — insider scos)
            "score_options":         int(r.get("score_options") or 0),
            "score_short":           int(r.get("score_short") or r.get("score_short_interest") or 0),
            "score_sideways":        int(r.get("score_sideways") or r.get("score_short_flow") or 0),
            # Semnale text
            "volume_signal":         r.get("volume_signal") or "",
            "insider_signal":        r.get("insider_signal") or "",
            "short_squeeze_signal":  r.get("short_squeeze_signal") or "",
            "sideways_signal":       r.get("sideways_signal") or "",
            "thesis":                r.get("thesis") or "",
            # AI Analysis
            "ai_thesis_ro":          r.get("ai_thesis_ro") or "",
        })
    get_client().table("enriched").upsert(rows, on_conflict="enrich_date,ticker").execute()


def get_enriched(days_back: int = 1, min_score: int = 0) -> list[dict]:
    since = (date.today() - timedelta(days=days_back)).isoformat()
    for table in ["enriched_view", "enriched"]:
        try:
            res = (get_client().table(table).select("*")
                   .gte("enrich_date", since)
                   .gte("score", min_score)
                   .order("score", desc=True)
                   .execute())
            if res.data:
                seen, out = set(), []
                for row in res.data:
                    t = row["ticker"]
                    if t not in seen:
                        seen.add(t)
                        out.append(row)
                return out
        except Exception:
            continue
    return []


def get_ticker_history(ticker: str, limit: int = 30) -> list[dict]:
    for table in ["enriched_view", "enriched"]:
        try:
            res = (get_client().table(table).select("*")
                   .eq("ticker", ticker.upper())
                   .order("enrich_date", desc=True)
                   .limit(limit)
                   .execute())
            rows = res.data or []
            if rows:
                rows.reverse()
                return rows
        except Exception:
            continue
    return []


# ── SECTOR STATS (NOU v2) ─────────────────────────────────────────────────────

def get_sector_stats(days_back: int = 1) -> list[dict]:
    """
    Agregare sector → count tickers activi + avg vol_ratio + avg score.
    Folosit de heatmap-ul din Streamlit.
    """
    since = (date.today() - timedelta(days=days_back)).isoformat()
    try:
        res = (get_client().table("enriched")
               .select("sector,score,vol_ratio")
               .gte("enrich_date", since)
               .neq("sector", "")
               .execute())
        rows = res.data or []
        if not rows:
            return []
        from collections import defaultdict
        agg = defaultdict(lambda: {"count": 0, "score_sum": 0.0, "vol_sum": 0.0})
        for r in rows:
            s = r.get("sector") or "Unknown"
            agg[s]["count"]     += 1
            agg[s]["score_sum"] += float(r.get("score") or 0)
            agg[s]["vol_sum"]   += float(r.get("vol_ratio") or 0)
        return [
            {
                "sector":    sector,
                "count":     v["count"],
                "avg_score": round(v["score_sum"] / v["count"], 1),
                "avg_vol":   round(v["vol_sum"] / v["count"], 2),
                "in_play":   v["count"] >= 5,   # arhitectura: 5+ = "In Play"
            }
            for sector, v in sorted(agg.items(), key=lambda x: -x[1]["count"])
        ]
    except Exception as e:
        print(f"[sector_stats] eroare: {e}")
        return []


# ── PERSISTENCE (NOU v2) ──────────────────────────────────────────────────────

def get_persistence_stats(days_back: int = 21) -> list[dict]:
    """
    Câte zile a apărut fiecare ticker în scan în ultimele N zile.
    Whale footprint: apariții multiple = acumulare persistentă.
    """
    since = (date.today() - timedelta(days=days_back)).isoformat()
    try:
        res = (get_client().table("scan_results")
               .select("ticker,scan_date")
               .gte("scan_date", since)
               .execute())
        rows = res.data or []
        from collections import defaultdict
        count = defaultdict(set)
        for r in rows:
            count[r["ticker"]].add(r["scan_date"])
        return [
            {"ticker": t, "appearance_days": len(dates)}
            for t, dates in sorted(count.items(), key=lambda x: -len(x[1]))
            if len(dates) >= 2  # minim 2 apariții pentru a fi relevant
        ]
    except Exception as e:
        print(f"[persistence] eroare: {e}")
        return []


# ── WATCHLIST ─────────────────────────────────────────────────────────────────

def get_watchlist() -> list[dict]:
    res = (get_client().table("watchlist").select("ticker,added_at,notes")
           .order("added_at", desc=True).execute())
    return res.data or []


def add_to_watchlist(ticker: str, notes: str = ""):
    get_client().table("watchlist").upsert(
        {"ticker": ticker.upper(), "notes": notes},
        on_conflict="ticker"
    ).execute()


def remove_from_watchlist(ticker: str):
    get_client().table("watchlist").delete().eq("ticker", ticker.upper()).execute()


def get_watchlist_enriched() -> list[dict]:
    watchlist = get_watchlist()
    if not watchlist:
        return []
    tickers = [w["ticker"] for w in watchlist]
    for table in ["enriched_view", "enriched"]:
        try:
            res = (get_client().table(table).select("*")
                   .in_("ticker", tickers)
                   .order("enrich_date", desc=True)
                   .execute())
            rows = res.data or []
            if rows:
                seen, result = set(), []
                for row in rows:
                    t = row["ticker"]
                    if t not in seen:
                        seen.add(t)
                        result.append(row)
                return result
        except Exception:
            continue
    return []
