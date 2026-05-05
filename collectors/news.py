"""
News sentiment classification via RSS feeds + keyword analysis.
Detectează articole care menționează un ticker și clasifică sentiment (buy/sell/neutral).
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from app.utils.logger import log_warn

# RSS feeds (6 surse)
RSS_FEEDS = [
    ("Yahoo Finance", "https://feeds.finance.yahoo.com/rss/2.0/headline"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("CNBC", "https://feeds.cnbc.com/id/100003114/feed.rss"),
    ("Investing.com Stocks", "https://feeds.investing.com/stocks/"),
    ("Investing.com General", "https://feeds.investing.com/general/"),
    ("TechCrunch", "https://feeds.feedburner.com/TechCrunch/"),
]

# BUY signal keywords (copiate din Scanner MVP)
BUY_KEYWORDS = [
    "beats", "beat", "exceeds", "surpasses", "tops estimates",
    "raises guidance", "raises forecast", "raises outlook",
    "record revenue", "record earnings", "record profit",
    "fda approves", "fda approval", "fda clears", "approved",
    "wins contract", "awarded contract", "secures contract",
    "acquires", "acquisition", "merger agreement",
    "buyback", "share repurchase",
    "upgrade", "price target raised", "outperform",
    "strong quarter", "strong results", "better than expected",
    "partnership", "strategic agreement", "joint venture",
    "dividend increase", "special dividend",
    "new contract", "major deal", "landmark deal",
]

# SELL signal keywords
SELL_KEYWORDS = [
    "misses", "miss", "below estimates", "disappoints",
    "cuts guidance", "lowers guidance", "cuts outlook",
    "profit warning", "revenue warning",
    "offering", "secondary offering", "dilution", "shelf registration",
    "investigation", "probe", "subpoena", "charged",
    "lawsuit", "sued", "legal action", "settlement",
    "layoffs", "job cuts", "restructuring", "downsizing",
    "downgrade", "price target cut", "underperform", "sell rating",
    "recall", "product recall", "safety issue",
    "ceo resigns", "cfo leaves", "executive departure",
    "fda rejects", "fda rejection", "clinical failure", "trial failure",
    "revenue decline", "loss widens", "margin compression",
]

# Categorii signal (categoria evenimentului)
TRIGGER_CATEGORY_MAP = {
    "earnings": ["beats", "beat", "misses", "miss", "results", "q3", "q4", "eps"],
    "guidance": ["raises guidance", "cuts guidance", "outlook", "forecast"],
    "contract": ["contract", "award", "wins", "customer"],
    "mna": ["acquisition", "merger", "acquires", "deal", "buyback"],
    "fda": ["fda", "clinical", "approval", "rejection"],
    "legal": ["lawsuit", "lawsuit", "investigation", "settlement", "charged"],
    "insider": ["insider", "ceo", "cfo", "executive"],
    "offering": ["offering", "dilution", "secondary"],
    "macro": ["tariff", "interest rate", "inflation", "federal reserve"],
}


def get_news_sentiment(ticker: str) -> dict:
    """
    Caută articole din RSS care menționează ticker-ul.
    Clasifică sentiment și categoria evenimentului.

    Return: {
        "news_signal":    "buy" | "sell" | "neutral" | None,
        "news_headline":  str | None,   # titlul principal
        "news_category":  str | None,   # earnings, contract, fda, etc.
    }
    """
    ticker = (ticker or "").upper()
    if not ticker:
        return {"news_signal": None, "news_headline": None, "news_category": None}

    articles = _fetch_articles()
    if not articles:
        return {"news_signal": None, "news_headline": None, "news_category": None}

    # Filtrează articole care menționează ticker
    relevant = []
    for article in articles:
        if _contains_ticker(article.get("title", ""), ticker):
            relevant.append(article)

    if not relevant:
        return {"news_signal": None, "news_headline": None, "news_category": None}

    # Clasifică sentimentul articolului cea mai relevantă
    best_article = relevant[0]  # prima menționare e cea mai relevantă
    title = best_article.get("title", "").lower()

    # Count BUY vs SELL keywords
    buy_count = sum(1 for kw in BUY_KEYWORDS if kw in title)
    sell_count = sum(1 for kw in SELL_KEYWORDS if kw in title)

    # Determină semnal
    if buy_count > sell_count:
        signal = "buy"
    elif sell_count > buy_count:
        signal = "sell"
    else:
        signal = "neutral" if (buy_count + sell_count > 0) else None

    # Determină categoria
    category = _classify_category(title)

    return {
        "news_signal": signal,
        "news_headline": best_article.get("title"),
        "news_category": category,
    }


def _fetch_articles() -> list[dict]:
    """
    Fetch articole din RSS feeds (15 per feed, deduplicate).
    """
    articles = []
    seen_titles = set()

    for feed_name, feed_url in RSS_FEEDS:
        try:
            resp = requests.get(feed_url, timeout=5)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            # Iterate over items
            items = root.findall(".//item")
            for item in items[:15]:  # Limit 15 per feed
                title_elem = item.find("title")
                link_elem = item.find("link")
                title = title_elem.text if title_elem is not None else ""
                link = link_elem.text if link_elem is not None else ""

                if title and title not in seen_titles:
                    seen_titles.add(title)
                    articles.append({
                        "title": title,
                        "link": link,
                        "source": feed_name,
                    })
        except Exception as e:
            log_warn(f"[News] {feed_name} RSS fetch failed: {e}")
            continue

    return articles


def _contains_ticker(text: str, ticker: str) -> bool:
    """
    Verifică dacă text menționează ticker-ul explicit.
    Caută: $TICKER sau [ TICKER ] cu limite de cuvânt.
    """
    text_upper = text.upper()
    # Caută $TICKER sau (TICKER) sau TICKER cu spații
    import re
    pattern = rf"(\${ticker}|[()\s]{ticker}[()\s])"
    return bool(re.search(pattern, text_upper))


def _classify_category(title: str) -> str | None:
    """
    Clasifică articolul în una din categorii pe baza keywords.
    """
    title_lower = title.lower()

    for category, keywords in TRIGGER_CATEGORY_MAP.items():
        if any(kw in title_lower for kw in keywords):
            return category

    return None
