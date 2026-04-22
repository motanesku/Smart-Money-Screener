"""
Toate operațiunile cu Supabase.
"""
import os
from datetime import date, timedelta
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]


def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── UNIVERSE ─────────────────────────────────────────────────────────────────

def save_universe(tickers: list[dict]):
    sb = get_client()
    sb.table("universe").upsert(tickers, on_conflict="ticker").execute()


def get_universe() -> list[dict]:
    sb  = get_client()
    res = sb.table("universe").select("ticker,company_name,sector,market_cap,avg_volume").execute()
    return res.data


# ── SCAN ─────────────────────────────────────────────────────────────────────

def save_scan_results(results: list[dict]):
    if not results:
        return
    sb    = get_client()
    today = date.today().isoformat()
    rows  = [{**r, "scan_date": today} for r in results]
    sb.table("scan_results").upsert(rows, on_conflict="scan_date,ticker").execute()


def get_scan_results(days_back: int = 1) -> list[dict]:
    sb    = get_client()
    since = (date.today() - timedelta(days=days_back)).isoformat()
    res   = (
        sb.table("scan_results")
        .select("*")
        .gte("scan_date", since)
        .order("vol_ratio", desc=True)
        .execute()
    )
    return res.data


# ── ENRICH ───────────────────────────────────────────────────────────────────

def save_enriched(results: list[dict]):
    if not results:
        return
    sb    = get_client()
    today = date.today().isoformat()
    rows  = [{**r, "enrich_date": today} for r in results]
    sb.table("enriched").upsert(rows, on_conflict="enrich_date,ticker").execute()


def get_enriched(days_back: int = 1, min_score: int = 0) -> list[dict]:
    sb    = get_client()
    since = (date.today() - timedelta(days=days_back)).isoformat()
    res   = (
        sb.table("enriched")
        .select("*")
        .gte("enrich_date", since)
        .gte("score", min_score)
        .order("score", desc=True)
        .execute()
    )
    return res.data


# ── WATCHLIST ────────────────────────────────────────────────────────────────

def get_watchlist() -> list[dict]:
    sb  = get_client()
    res = sb.table("watchlist").select("ticker,added_at,notes").order("added_at", desc=True).execute()
    return res.data


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
    sb       = get_client()
    watchlist = get_watchlist()
    if not watchlist:
        return []
    tickers = [w["ticker"] for w in watchlist]
    res     = (
        sb.table("enriched")
        .select("*")
        .in_("ticker", tickers)
        .order("enrich_date", desc=True)
        .execute()
    )
    seen, result = set(), []
    for row in res.data:
        if row["ticker"] not in seen:
            seen.add(row["ticker"])
            result.append(row)
    return result
