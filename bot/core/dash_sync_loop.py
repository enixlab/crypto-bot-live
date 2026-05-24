"""Boucle de synchronisation du dashboard — DÉCOUPLÉE des bots.

Remplace le push qui était fait par l'orchestrateur legacy `bot.main` (base_bot.py),
désactivé le 2026-05-24 car il collisionnait avec les bots zaid_fleet dédiés.

Toutes les ~3 min :
  1. export_dashboard_data() relit les 5 state files de data/ et régénère dashboard_data.js
  2. push_dashboard_to_github() force-push sur la branche data-feed

C'est le SEUL processus qui fait des opérations git → pas de concurrence avec les bots
(qui se contentent d'écrire leurs *_state.json, gitignorés).

Tâche planifiée dédiée : EnixDashSync (cf. add_dash_sync.ps1).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent  # crypto-bot-live/
sys.path.insert(0, str(_root / "bot"))

# Charge .env (GITHUB_TOKEN nécessaire pour le push)
for _c in (_root / ".env",):
    if _c.exists():
        for _l in _c.read_text(encoding="utf-8").splitlines():
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from core.dashboard_export import export_dashboard_data
from core.sync_dashboard import push_dashboard_to_github

BOT_KEYS = [
    "sentiment_ls_v3_lo",
    "confluence_reverse",
    "ultimate_v2_reverse",
    "sentiment_ls_v3",
    "sentiment_ls_v3_tp",
]
INTERVAL_SEC = 180


def main():
    print(f"[dash_sync] start — {len(BOT_KEYS)} bots, push toutes les {INTERVAL_SEC}s")
    if not (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")):
        print("[dash_sync] ⚠️ GITHUB_TOKEN absent du .env — le push échouera")
    while True:
        try:
            export_dashboard_data(
                bot_keys=BOT_KEYS,
                data_dir=str(_root / "data"),
                dashboard_dir=str(_root / "dashboard"),
            )
            ok = push_dashboard_to_github(_root, min_interval_sec=0)
            print(f"[dash_sync] {time.strftime('%H:%M:%S')} export OK | push={'OK' if ok else 'FAIL'}")
        except Exception as e:
            print(f"[dash_sync] err: {e}")
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
