"""
Toate operațiunile cu Supabase.
"""
import os
from datetime import date, timedelta
from supabase import create_client, Client


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()


_client: Client | None = None


def get_client() -> Client:
    global _client

    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL lipsește")
    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_KEY lipsește")
    if not SUPABASE_URL.startswith("https://"):
        raise RuntimeError("SUPABASE_URL este invalid. Trebuie să înceapă cu https://")

    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ── UNIVERSE ─────────────────────────────────────────────────────────────────

def save_universe(tickers: list[dict]):
    if not tickers:
        return
    sb = get_client()
    sb.table("universe").upsert(tickers, on_conflict="ticker").execute()



def get_universe() -> list[dict]:
    sb = get_client()
    res = sb.table("universe").select("ticker,company_name,sector,market_cap,avg_volume").execute()
    return res.data or []


# ── SCAN ─────────────────────────────────────────────────────────────────────

def save_scan_results(results: list[dict]):
    if not results:
        return
    sb = get_client()
    today = date.today().isoformat()
    rows = [{**r, "scan_date": today} for r in results]
    sb.table("scan_results").upsert(rows, on_conflict="scan_date,ticker").execute()



def get_scan_results(days_back: int = 1) -> list[dict]:
    sb = get_client()
    since = (date.today() - timedelta(days=days_back)).isoformat()
    res = (
        sb.table("scan_results")
        .select("*")
        .gte("scan_date", since)
        .order("vol_ratio", desc=True)
        .execute()
    )
    return res.data or []


# ── ENRICH ───────────────────────────────────────────────────────────────────

def save_enriched(results: list[dict]):
    if not results:
        return

    sb = get_client()
    today = date.today().isoformat()

    allowed_keys = {
        "ticker",
        "price",
        "volume",
        "avg_volume_20d",
        "vol_ratio",
        "insider_buys_90d",
        "insider_buy_value",
        "insider_sells_90d",
        "inst_ownership_pct",
        "pe_ratio",
        "short_interest_pct",
        "market_cap",
        "sector",
        "industry",
        "score",
    }

    rows = []
    for r in results:
        clean = {k: v for k, v in r.items() if k in allowed_keys}
        clean["enrich_date"] = today
        rows.append(clean)

    sb.table("enriched").upsert(rows, on_conflict="enrich_date,ticker").execute()



def get_enriched(days_back: int = 1, min_score: int = 0) -> list[dict]:
    sb = get_client()
    since = (date.today() - timedelta(days=days_back)).isoformat()
    res = (
        sb.table("enriched")
        .select("*")
        .gte("enrich_date", since)
        .gte("score", min_score)
        .order("score", desc=True)
        .execute()
    )
    return res.data or []


# ── WATCHLIST ────────────────────────────────────────────────────────────────

def get_watchlist() -> list[dict]:
    sb = get_client()
    res = sb.table("watchlist").select("ticker,added_at,notes").order("added_at", desc=True).execute()
    return res.data or []



def add_to_watchlist(ticker: str, notes: str = ""):
    sb = get_client()
    sb.table("watchlist").upsert(
        {"ticker": ticker.upper(), "notes": notes},
        on_conflict="ticker"
    ).execute()



def remove_from_watchlist(ticker: str):
    sb = get_client()
    sb.table("watchlist").delete().eq("ticker", ticker.upper()).execute()



def get_watchlist_enriched() -> list[dict]:
    sb = get_client()
    watchlist = get_watchlist()
    if not watchlist:
        return []

    tickers = [w["ticker"] for w in watchlist]
    res = (
        sb.table("enriched")
        .select("*")
        .in_("ticker", tickers)
        .order("enrich_date", desc=True)
        .execute()
    )

    seen, result = set(), []
    for row in (res.data or []):
        ticker = row.get("ticker")
        if ticker and ticker not in seen:
            seen.add(ticker)
            result.append(row)
    return result
