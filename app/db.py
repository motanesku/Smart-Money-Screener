"""
DB v9 — modificări:
- get_ticker_history: limit 30 zile în loc de 10
- enriched_view cu DISTINCT ON pentru deduplicare
- fallback robust la tabelă dacă view-ul lipsește
- insider_sell_value adăugat în save_enriched
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
    if not tickers: return
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
    if not results: return
    today = date.today().isoformat()
    rows  = [{
        "scan_date":      today,
        "ticker":         (r.get("ticker") or "").upper(),
        "price":          r.get("price"),
        "volume":         int(r.get("volume") or 0),
        "avg_volume_20d": int(r.get("avg_volume_20d") or r.get("avg_volume") or 0),
        "vol_ratio":      r.get("vol_ratio"),
    } for r in results]
    get_client().table("scan_results").upsert(rows, on_conflict="scan_date,ticker").execute()


def get_scan_results(days_back: int = 1) -> list[dict]:
    since = (date.today() - timedelta(days=days_back)).isoformat()
    res   = (get_client().table("scan_results").select("*")
             .gte("scan_date", since).order("vol_ratio", desc=True).execute())
    return res.data or []


# ── ENRICH ────────────────────────────────────────────────────────────────────

def save_enriched(results: list[dict]):
    if not results: return
    today = date.today().isoformat()
    rows  = []
    for r in results:
        rows.append({
            "enrich_date":            today,
            "ticker":                 (r.get("ticker") or "").upper(),
            "company_name":           r.get("company_name") or "",
            "sector":                 r.get("sector") or "",
            "industry":               r.get("industry") or "",
            "market_cap":             int(r.get("market_cap") or 0),
            "price":                  r.get("price"),
            "volume":                 int(r.get("volume") or 0),
            "avg_volume_20d":         int(r.get("avg_volume_20d") or r.get("avg_volume") or 0),
            "vol_ratio":              r.get("vol_ratio"),
            "insider_buys_90d":       int(r.get("insider_buys_90d") or 0),
            "insider_buy_value":      float(r.get("insider_buy_value") or 0),
            "insider_sells_90d":      int(r.get("insider_sells_90d") or 0),
            "insider_sell_value":     float(r.get("insider_sell_value") or 0),
            "inst_ownership_pct":     r.get("inst_ownership_pct"),
            "pe_ratio":               r.get("pe_ratio"),
            "short_interest_pct":     r.get("short_interest_pct"),
            "score":                  int(r.get("score") or 0),
            "market_cap":             int(r.get("market_cap") or 0),
            "score_volume":           int(r.get("score_volume") or 0),
            "score_insider":          0,
            "score_insider_quality":  0,
            "score_ownership":        int(r.get("score_ownership") or 0),
            "score_short_interest":   int(r.get("score_short_interest") or 0),
            "score_short_flow":       int(r.get("score_short_flow") or 0),
            "score_fundamental":      0,
            "score_penalty":          0,
            "volume_signal":          r.get("volume_signal") or "",
            "insider_signal":         r.get("insider_signal") or "",
            "short_signal":           r.get("short_signal") or "",
            "ownership_signal_text":  r.get("ownership_signal") or "",
            "thesis":                 r.get("thesis") or "",
            "top_insider_role":       r.get("top_insider_role") or "Unknown",
            "ownership_form":         r.get("ownership_form") or "",
            "ownership_holder":       r.get("ownership_holder") or "",
            "ownership_pct":          r.get("ownership_pct"),
            "ownership_signal":       r.get("ownership_signal") or "",
            "short_sale_volume":      int(r.get("short_sale_volume") or 0),
            "total_volume_reported":  int(r.get("total_volume_reported") or 0),
            "short_sale_ratio":       r.get("short_sale_ratio"),
            "short_flow_signal":      r.get("short_flow_signal") or
                                      r.get("short_flow_signal_text") or "",
            "beta":                   r.get("beta"),
        })
    get_client().table("enriched").upsert(rows, on_conflict="enrich_date,ticker").execute()


def _query_enriched(table: str, query_fn) -> list[dict]:
    try:
        res = query_fn(get_client().table(table))
        return res.data or []
    except Exception:
        return []


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
                # Deduplicare client-side ca safety net
                seen, out = set(), []
                for row in res.data:
                    t = row["ticker"]
                    if t not in seen:
                        seen.add(t); out.append(row)
                return out
        except Exception:
            continue
    return []


def get_ticker_history(ticker: str, limit: int = 30) -> list[dict]:
    """Istoric 30 de zile pentru un ticker — pentru grafice și trending."""
    for table in ["enriched_view", "enriched"]:
        try:
            res = (get_client().table(table).select("*")
                   .eq("ticker", ticker.upper())
                   .order("enrich_date", desc=True)
                   .limit(limit)
                   .execute())
            rows = res.data or []
            if rows:
                rows.reverse()  # cronologic
                return rows
        except Exception:
            continue
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
    if not watchlist: return []
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
                        seen.add(t); result.append(row)
                return result
        except Exception:
            continue
    return []
