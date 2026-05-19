"""sentiment_v1 — bot multi-crypto basé sur sentiment LLM.

Premier bot de la flotte crypto LIVE. Univers de départ : LINK, SUI, INJ.
Identique à `sentiment_ls_v3` du paper bot mais exécution Hyperliquid.
"""
from __future__ import annotations

import logging
from .base_bot import BaseBot
from ..core.news_feed import fetch_articles_for_universe
from ..core.sentiment import aggregate_universe

log = logging.getLogger(__name__)


class SentimentV1Bot(BaseBot):
    bot_id = "sentiment_v1"
    bot_name = "Sentiment V1"

    def fetch_signals(self) -> dict:
        articles = fetch_articles_for_universe(self.universe, lookback_hours=6)
        return aggregate_universe(articles)
