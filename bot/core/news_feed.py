"""News feed — agrégateur CryptoNews + CryptoPanic.

Pull les articles récents par crypto. Renvoie une liste structurée
qui sera scorée par sentiment.py.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import feedparser  # type: ignore
import requests

log = logging.getLogger(__name__)


@dataclass
class Article:
    coin: str           # symbole crypto associé (ex "LINK")
    title: str
    summary: str
    url: str
    source: str
    published_ts: int   # unix epoch


# Tickers crypto — univers OFFICIEL du PDF Sentiment Cartography (planche V)
# 19 mid-caps news-driven : assez gros pour être liquides, assez petits pour que les news impactent
DEFAULT_UNIVERSE = [
    "BTC", "ETH", "XRP",          # large caps de référence
    "AAVE", "SUI", "INJ",          # DeFi + L1 narratifs
    "LDO", "AVAX", "LINK", "UNI",  # DeFi blue chips
    "NEAR", "APT", "ARB", "OP",    # L1/L2 next-gen
    "DOGE",                        # memecoin pricé sur news
    "FET", "RNDR",                 # narratif AI
    "FIL", "ONDO",                 # storage + RWA
    "HBAR",                        # Hedera Hashgraph (ajout Enix)
]


def fetch_cryptopanic(coin: str, api_key: str, lookback_hours: int = 6) -> list[Article]:
    """CryptoPanic REST API : https://cryptopanic.com/developers/api/

    Free tier OK pour faible volume. ~200 req/jour gratuit.
    """
    if not api_key:
        return []
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        "auth_token": api_key,
        "currencies": coin,
        "filter": "rising",
        "kind": "news",
        "public": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("cryptopanic %s err: %s", coin, e)
        return []

    cutoff = time.time() - lookback_hours * 3600
    out: list[Article] = []
    for p in data.get("results", []):
        pub = datetime.fromisoformat(p["published_at"].replace("Z", "+00:00")).timestamp()
        if pub < cutoff:
            continue
        out.append(Article(
            coin=coin,
            title=p.get("title", ""),
            summary=p.get("title", ""),
            url=p.get("url", ""),
            source="cryptopanic:" + p.get("source", {}).get("title", ""),
            published_ts=int(pub),
        ))
    return out


# Flux RSS publics gratuits — étendu pour couvrir tous les altcoins
RSS_SOURCES = {
    "cointelegraph": "https://cointelegraph.com/rss",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "decrypt": "https://decrypt.co/feed",
    "thedefiant": "https://thedefiant.io/feed",
    "cryptonews": "https://cryptonews.com/news/feed",
    "newsbtc": "https://www.newsbtc.com/feed/",
    "bitcoinmagazine": "https://bitcoinmagazine.com/feed",
    "crypto_news": "https://crypto.news/feed/",
    "theblock": "https://www.theblock.co/rss.xml",
    "blockworks": "https://blockworks.co/feed/",
    "cryptopolitan": "https://www.cryptopolitan.com/feed/",
    "ambcrypto": "https://ambcrypto.com/feed/",
    "u_today": "https://u.today/rss",
    "bitcoinist": "https://bitcoinist.com/feed/",
    "cryptoglobe": "https://www.cryptoglobe.com/feed/",
    "cryptopotato": "https://cryptopotato.com/feed/",
    "bitcoinerx": "https://bitcoinerx.com/feed/",
    "coinspeaker": "https://www.coinspeaker.com/feed/",
    "beincrypto": "https://beincrypto.com/feed/",
    "cryptobriefing": "https://cryptobriefing.com/feed/",
}


def fetch_google_news_for_coin(coin: str, lookback_hours: int = 12) -> list[Article]:
    """Google News RSS — recherche par mot-clé. Gratuit, sans clé API.

    Donne 10-30 articles par crypto, beaucoup plus que les RSS génériques.
    """
    import urllib.parse
    cutoff = time.time() - lookback_hours * 3600
    out: list[Article] = []
    # Mapping ticker → nom complet pour meilleure recherche
    COIN_NAMES = {
        "BTC": "Bitcoin", "ETH": "Ethereum", "XRP": "Ripple XRP",
        "AAVE": "Aave crypto", "SUI": "Sui crypto", "INJ": "Injective crypto",
        "LDO": "Lido finance", "AVAX": "Avalanche AVAX", "LINK": "Chainlink",
        "UNI": "Uniswap", "NEAR": "Near Protocol", "APT": "Aptos crypto",
        "ARB": "Arbitrum", "OP": "Optimism crypto", "DOGE": "Dogecoin",
        "FET": "Fetch.ai", "RNDR": "Render token", "FIL": "Filecoin",
        "ONDO": "Ondo Finance", "HBAR": "Hedera Hashgraph",
    }
    query = COIN_NAMES.get(coin, coin) + " crypto"
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        log.warning("google news %s err: %s", coin, e)
        return []
    for entry in feed.entries[:15]:
        pub = entry.get("published_parsed") or entry.get("updated_parsed")
        if not pub:
            continue
        pub_ts = time.mktime(pub)
        if pub_ts < cutoff:
            continue
        out.append(Article(
            coin=coin,
            title=entry.get("title", ""),
            summary=entry.get("summary", "")[:300],
            url=entry.get("link", ""),
            source="google_news",
            published_ts=int(pub_ts),
        ))
    return out


def fetch_rss(coin: str, lookback_hours: int = 6) -> list[Article]:
    """Pull RSS feeds publics et filtre par mention du ticker dans le titre/résumé."""
    cutoff = time.time() - lookback_hours * 3600
    out: list[Article] = []
    for src, url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            log.warning("RSS %s err: %s", src, e)
            continue
        for entry in feed.entries[:30]:
            text = (entry.get("title", "") + " " + entry.get("summary", "")).upper()
            # Filtre simple : le ticker doit apparaître (entouré d'espaces, $, ou en début/fin)
            tick = coin.upper()
            if tick not in text:
                continue
            # Heuristique anti-faux-positif : éviter "LINK" dans "LINKED"
            words = text.replace("$", " ").replace(",", " ").replace(".", " ").split()
            if tick not in words:
                continue
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            if not pub:
                continue
            pub_ts = time.mktime(pub)
            if pub_ts < cutoff:
                continue
            out.append(Article(
                coin=coin,
                title=entry.get("title", ""),
                summary=entry.get("summary", ""),
                url=entry.get("link", ""),
                source="rss:" + src,
                published_ts=int(pub_ts),
            ))
    return out


def fetch_articles_for_coin(coin: str, lookback_hours: int = 12, cryptopanic_key: Optional[str] = None) -> list[Article]:
    cryptopanic_key = cryptopanic_key or os.environ.get("CRYPTOPANIC_API_KEY", "")
    articles: list[Article] = []
    articles += fetch_cryptopanic(coin, cryptopanic_key, lookback_hours)
    articles += fetch_rss(coin, lookback_hours)
    articles += fetch_google_news_for_coin(coin, lookback_hours)  # ← +10-30 articles par crypto !
    # Dédoublonnage par URL et titre
    seen_urls, seen_titles = set(), set()
    dedup = []
    for a in articles:
        if a.url in seen_urls or a.title.lower() in seen_titles:
            continue
        seen_urls.add(a.url)
        seen_titles.add(a.title.lower())
        dedup.append(a)
    # Limiter à max 20 articles par coin (sinon trop de tokens DeepSeek)
    return dedup[:20]


def fetch_articles_for_universe(coins: list[str] | None = None, lookback_hours: int = 6) -> dict[str, list[Article]]:
    coins = coins or DEFAULT_UNIVERSE
    return {c: fetch_articles_for_coin(c, lookback_hours) for c in coins}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    coin = sys.argv[1] if len(sys.argv) > 1 else "LINK"
    arts = fetch_articles_for_coin(coin, lookback_hours=24)
    print(f"{coin}: {len(arts)} articles")
    for a in arts[:5]:
        print(f"  [{a.source}] {a.title}")
