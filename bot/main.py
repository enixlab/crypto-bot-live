"""Entrée principale — orchestrateur de la flotte.

Usage :
    python -m bot.main --mode paper
    python -m bot.main --mode live --network testnet
    python -m bot.main --mode live --network mainnet
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from .bots.sentiment_v1 import SentimentV1Bot
from .core.state import StateStore
from .core.strategy import StrategyParams
from .core.hyperliquid_client import HyperliquidClient

log = logging.getLogger(__name__)


def build_fleet(mode: str, network: str, gcs_bucket: str | None) -> list:
    """Construit les bots de la flotte. Pour MVP : sentiment_v1 seul."""
    params = StrategyParams(
        leverage=int(os.environ.get("LEVERAGE", "3")),
        max_hold_hours=72,
        exit_band_pct=0.01,
        tp_pct=0.05,
        sl_pct=-0.08,
    )

    hl = None
    paper_mode = (mode == "paper")
    if not paper_mode:
        os.environ["HYPERLIQUID_NETWORK"] = network
        hl = HyperliquidClient.from_env()
        check = hl.check()
        log.info("HL check: %s", check)

    fleet = []
    # Univers par défaut = 19 cryptos du PDF Sentiment Cartography
    DEFAULT_19 = "BTC,ETH,XRP,AAVE,SUI,INJ,LDO,AVAX,LINK,UNI,NEAR,APT,ARB,OP,DOGE,FET,RNDR,FIL,ONDO"
    universe = os.environ.get("BOT_UNIVERSE", DEFAULT_19).split(",")
    bot1 = SentimentV1Bot(
        universe=universe,
        params=params,
        store=StateStore("sentiment_v1", gcs_bucket=gcs_bucket),
        hl_client=hl,
        paper_mode=paper_mode,
    )
    fleet.append(bot1)
    return fleet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--once", action="store_true", help="Un seul cycle (pour Cloud Scheduler cron)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    load_dotenv()

    if args.mode == "live" and args.network == "mainnet":
        log.warning("⚠️  MODE LIVE MAINNET — VRAI ARGENT")

    gcs_bucket = os.environ.get("GCS_BUCKET")
    fleet = build_fleet(args.mode, args.network, gcs_bucket)

    if args.once:
        for bot in fleet:
            try:
                bot.cycle()
            except Exception as e:
                log.exception("bot %s err: %s", bot.bot_id, e)
        return 0

    # Mode loop (dev local)
    import time
    cycle_minutes = int(os.environ.get("CYCLE_MINUTES", "10"))
    while True:
        for bot in fleet:
            try:
                bot.cycle()
            except Exception as e:
                log.exception("bot %s err: %s", bot.bot_id, e)
        log.info("Sleeping %d minutes...", cycle_minutes)
        time.sleep(cycle_minutes * 60)


if __name__ == "__main__":
    sys.exit(main())
