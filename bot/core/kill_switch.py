"""Kill switch — sécurité ultime contre drawdown.

Si l'equity tombe sous (peak * (1 - KILL_SWITCH_DD_PCT)) :
1. Ferme toutes les positions ouvertes
2. Marque le bot OFFLINE dans le state
3. Envoie alerte Telegram
4. Refuse toute nouvelle entrée jusqu'à reset manuel
"""
from __future__ import annotations

import logging
import os
from .state import BotState

log = logging.getLogger(__name__)


def check_kill_switch(state: BotState, dd_threshold_pct: float = -0.15) -> bool:
    if state.peak_equity <= 0:
        return False
    dd = (state.equity - state.peak_equity) / state.peak_equity
    if dd <= dd_threshold_pct:
        log.error("KILL SWITCH TRIGGERED: dd=%.2f%% (threshold=%.2f%%)",
                  dd * 100, dd_threshold_pct * 100)
        return True
    return False


def send_telegram_alert(message: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log.warning("Telegram non configuré, alert non envoyée")
        return False
    try:
        import requests
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        return r.ok
    except Exception as e:
        log.warning("Telegram err: %s", e)
        return False
