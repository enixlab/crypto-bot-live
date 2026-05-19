"""4 bots crypto avec stratégies différentes.

Chaque bot hérite de BaseBot mais avec ses propres paramètres
et son propre filtre d'entrée.
"""
from __future__ import annotations

import logging
from .base_bot import BaseBot
from ..core.news_feed import fetch_articles_for_universe
from ..core.sentiment import aggregate_universe
from ..core.strategy import StrategyParams

log = logging.getLogger(__name__)


# ===== 1. LS V3 — Stratégie standard du PDF =====
class LSV3Bot(BaseBot):
    """Long/Short standard basé sur sentiment LLM (la base du PDF Sentiment Cartography).

    Seuils : LONG ≥ 0.65 / SHORT ≤ 0.40
    MAX_HOLD : 72h, exit_band ±1%
    TP/SL : +5%/-8%
    """
    bot_id = "sentiment_ls_v3"
    bot_name = "LS V3"

    @staticmethod
    def default_params() -> StrategyParams:
        return StrategyParams(
            long_threshold=0.65,
            short_threshold=0.40,
            max_hold_hours=72,
            exit_band_pct=0.01,
            tp_pct=0.05,
            sl_pct=-0.08,
        )

    def fetch_signals(self) -> dict:
        articles = fetch_articles_for_universe(self.universe, lookback_hours=6)
        return aggregate_universe(articles)


# ===== 2. Ultimate V2 — Conviction haute =====
class UltimateV2Bot(BaseBot):
    """Trade UNIQUEMENT les signaux très forts (conviction haute).

    Seuils plus stricts : LONG ≥ 0.75 / SHORT ≤ 0.30
    → Moins de trades, mais ceux qu'il prend sont plus sûrs.
    Profit Factor visé : > 1.5
    """
    bot_id = "ultimate_v2"
    bot_name = "Ultimate V2"

    @staticmethod
    def default_params() -> StrategyParams:
        return StrategyParams(
            long_threshold=0.75,
            short_threshold=0.30,
            max_hold_hours=96,
            exit_band_pct=0.015,
            tp_pct=0.07,
            sl_pct=-0.08,
            min_articles_per_coin=3,
        )

    def fetch_signals(self) -> dict:
        articles = fetch_articles_for_universe(self.universe, lookback_hours=12)
        return aggregate_universe(articles)


# ===== 3. LS V3 TP — Scalp court terme =====
class ScalpTPBot(BaseBot):
    """Scalp court terme : positions tenues max 24h, exit band ±0.5%.

    Beaucoup plus de rotations, gains plus petits mais plus fréquents.
    """
    bot_id = "sentiment_ls_v3_tp"
    bot_name = "LS V3 TP"

    @staticmethod
    def default_params() -> StrategyParams:
        return StrategyParams(
            long_threshold=0.65,
            short_threshold=0.40,
            max_hold_hours=24,
            exit_band_pct=0.005,
            tp_pct=0.03,
            sl_pct=-0.05,
            cycle_minutes=120,
        )

    def fetch_signals(self) -> dict:
        articles = fetch_articles_for_universe(self.universe, lookback_hours=3)
        return aggregate_universe(articles)


# ===== 4. Confluence — Multi-signaux =====
class ConfluenceBot(BaseBot):
    """Demande la CONFLUENCE de plusieurs signaux pour ouvrir.

    Critères stricts :
      - Au moins 5 articles trouvés (vs 2 minimum standard)
      - Sentiment très tranché (≥0.70 ou ≤0.35)
      - Évite les coins en VETO technique
    """
    bot_id = "confluence"
    bot_name = "CONFLUENCE"

    @staticmethod
    def default_params() -> StrategyParams:
        return StrategyParams(
            long_threshold=0.70,
            short_threshold=0.35,
            max_hold_hours=72,
            exit_band_pct=0.01,
            tp_pct=0.05,
            sl_pct=-0.06,
            min_articles_per_coin=5,
            veto_pct=0.025,
        )

    def fetch_signals(self) -> dict:
        articles = fetch_articles_for_universe(self.universe, lookback_hours=8)
        return aggregate_universe(articles)
