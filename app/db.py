"""
Toate operațiunile cu Supabase.
Compatibil cu schema existentă și cu migration incrementală.
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


def save_universe(tickers: list[dict]):
    if not tickers:
        return
    rows = []
    for t in tickers:
        rows.append({
            "ticker": (t.get("ticker") or "").upper(),
            "company_name": t.get("company_name") or "",
            "exchange": t.get("exchange") or "",
            "sector": t.get("sector") or "",
            "industry": t.get("industry") or "",
            "market_cap": int(t.get("market_cap") or 0),
            "avg_volume": int(t.get("avg_volume") or t.get("avg_volume_20d") or 0),
        })
    sb = get_client()
    sb.table("universe").upsert(rows, on_conflict="ticker").execute()


def get_universe() -> list[dict]:
    sb = get_client()
    res = sb.table("universe").select("ticker,company_name,sector,industry,market_cap,avg_volume").execute()
    return res.data


def save_scan_results(results: list[dict]):
    if not results:
        return
    today = date.today().isoformat()
    rows = []
    for r in results:
        rows.append({
            "scan_date": today,
            "ticker": (r.get("ticker") or "").upper(),
            "price": r.get("price"),
            "volume": int(r.get("volume") or 0),
            "avg_volume_20d": int(r.get("avg_volume_20d") or r.get("avg_volume") or 0),
            "vol_ratio": r.get("vol_ratio"),
        })
    sb = get_client()
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


def save_enriched(results: list[dict]):
    if not results:
        return
    today = date.today().isoformat()
    rows = []
    for r in results:
        rows.append({
            "enrich_date": today,
            "ticker": (r.get("ticker") or "").upper(),
            "price": r.get("price"),
            "volume": int(r.get("volume") or 0),
            "avg_volume_20d": int(r.get("avg_volume_20d") or r.get("avg_volume") or 0),
            "vol_ratio": r.get("vol_ratio"),
            "insider_buys_90d": int(r.get("insider_buys_90d") or 0),
            "insider_buy_value": float(r.get("insider_buy_value") or 0),
            "insider_sells_90d": int(r.get("insider_sells_90d") or 0),
            "inst_ownership_pct": r.get("inst_ownership_pct"),
            "pe_ratio": r.get("pe_ratio"),
            "short_interest_pct": r.get("short_interest_pct"),
            "score": int(r.get("score") or 0),
            "market_cap": int(r.get("market_cap") or 0),
            "sector": r.get("sector") or "",
            "industry": r.get("industry") or "",
            "score_volume": int(r.get("score_volume") or 0),
            "score_insider": int(r.get("score_insider") or 0),
            "score_short_interest": int(r.get("score_short_interest") or 0),
            "score_fundamental": int(r.get("score_fundamental") or 0),
            "score_penalty": int(r.get("score_penalty") or 0),
            "volume_signal": r.get("volume_signal") or "",
            "insider_signal": r.get("insider_signal") or "",
            "short_signal": r.get("short_signal") or "",
            "thesis": r.get("thesis") or "",
            "score_insider_quality": int(r.get("insider_quality_score") or 0),
            "top_insider_role": r.get("top_insider_role") or "Unknown",
            "ownership_form": r.get("ownership_form") or "",
            "ownership_holder": r.get("ownership_holder") or "",
            "ownership_pct": r.get("ownership_pct"),
            "ownership_signal": r.get("ownership_signal") or "",
            "score_ownership": int(r.get("score_ownership") or 0),
            "short_sale_volume": int(r.get("short_sale_volume") or 0),
            "total_volume_reported": int(r.get("total_volume_reported") or 0),
            "short_sale_ratio": r.get("short_sale_ratio"),
            "short_flow_signal": r.get("short_flow_signal") or "",
            "score_short_flow": int(r.get("score_short_flow") or 0),
        })
    sb = get_client()
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


def get_ticker_history(ticker: str, limit: int = 10) -> list[dict]:
    sb = get_client()
    res = (
        sb.table("enriched")
        .select("enrich_date,ticker,score,vol_ratio,insider_buys_90d,insider_buy_value,insider_sells_90d,short_interest_pct,pe_ratio,score_volume,score_insider,score_short_interest,score_fundamental,score_penalty,volume_signal,insider_signal,short_signal,thesis,score_insider_quality,top_insider_role,ownership_form,ownership_holder,ownership_pct,ownership_signal,score_ownership,short_sale_volume,total_volume_reported,short_sale_ratio,short_flow_signal,score_short_flow")
        .eq("ticker", ticker.upper())
        .order("enrich_date", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    rows.reverse()
    return rows


def get_watchlist() -> list[dict]:
    sb = get_client()
    res = sb.table("watchlist").select("ticker,added_at,notes").order("added_at", desc=True).execute()
    return res.data


def add_to_watchlist(ticker: str, notes: str = ""):
    sb = get_client()
    sb.table("watchlist").upsert({"ticker": ticker.upper(), "notes": notes}, on_conflict="ticker").execute()


def remove_from_watchlist(ticker: str):
    sb = get_client()
    sb.table("watchlist").delete().eq("ticker", ticker.upper()).execute()


def get_watchlist_enriched() -> list[dict]:
    watchlist = get_watchlist()
    if not watchlist:
        return []
    tickers = [w["ticker"] for w in watchlist]
    sb = get_client()
    res = (
        sb.table("enriched")
        .select("*")
        .in_("ticker", tickers)
        .order("enrich_date", desc=True)
        .execute()
    )
    seen = set()
    result = []
    for row in (res.data or []):
        t = row["ticker"]
        if t not in seen:
            seen.add(t)
            result.append(row)
    return result
