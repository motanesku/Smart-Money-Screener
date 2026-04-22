"""
Toate operațiunile cu Supabase.
"""
import os
from datetime import date, timedelta
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]


def get_client() -> Client:
    if not SUPABASE_URL.startswith("https://"):
        raise ValueError("SUPABASE_URL trebuie sa inceapa cu https://")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── UNIVERSE ─────────────────────────────────────────────────────────────────

def save_universe(tickers: list[dict]):
    if not tickers:
        return
    sb = get_client()
    rows = []
    for t in tickers:
        rows.append({
            "ticker": t.get("ticker", "").upper(),
            "company_name": t.get("company_name", ""),
            "exchange": t.get("exchange", ""),
            "sector": t.get("sector", ""),
            "industry": t.get("industry", ""),
            "market_cap": int(t.get("market_cap") or 0),
            "avg_volume_20d": int(t.get("avg_volume_20d") or 0),
        })
    sb.table("universe").upsert(rows, on_conflict="ticker").execute()


def get_universe() -> list[dict]:
    sb = get_client()
    res = (
        sb.table("universe")
        .select("ticker,company_name,sector,market_cap,avg_volume_20d")
        .execute()
    )
    return res.data


# ── SCAN ─────────────────────────────────────────────────────────────────────

def save_scan_results(results: list[dict]):
    if not results:
        return
    sb = get_client()
    today = date.today().isoformat()
    rows = []
    for r in results:
        rows.append({
            "scan_date": today,
            "ticker": r.get("ticker", "").upper(),
            "price": r.get("price"),
            "volume": int(r.get("volume") or 0),
            "avg_volume_20d": int(r.get("avg_volume_20d") or 0),
            "vol_ratio": r.get("vol_ratio"),
        })
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
    return res.data


# ── ENRICH ───────────────────────────────────────────────────────────────────

def save_enriched(results: list[dict]):
    if not results:
        return
    sb = get_client()
    today = date.today().isoformat()
    rows = []
    for r in results:
        rows.append({
            "enrich_date": today,
            "ticker": r.get("ticker", "").upper(),
            "price": r.get("price"),
            "volume": int(r.get("volume") or 0),
            "avg_volume_20d": int(r.get("avg_volume_20d") or 0),
            "vol_ratio": r.get("vol_ratio"),
            "insider_buys_90d": int(r.get("insider_buys_90d") or 0),
            "insider_buy_value": float(r.get("insider_buy_value") or 0),
            "insider_sells_90d": int(r.get("insider_sells_90d") or 0),
            "inst_ownership_pct": r.get("inst_ownership_pct"),
            "pe_ratio": r.get("pe_ratio"),
            "short_interest_pct": r.get("short_interest_pct"),
            "market_cap": int(r.get("market_cap") or 0),
            "sector": r.get("sector", ""),
            "industry": r.get("industry", ""),
            "score": int(r.get("score") or 0),
        })
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
    return res.data


# ── WATCHLIST ────────────────────────────────────────────────────────────────

def get_watchlist() -> list[dict]:
    sb = get_client()
    res = (
        sb.table("watchlist")
        .select("ticker,added_at,notes")
        .order("added_at", desc=True)
        .execute()
    )
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

    seen = set()
    result = []
    for row in res.data:
        if row["ticker"] not in seen:
            seen.add(row["ticker"])
            result.append(row)
    return result
