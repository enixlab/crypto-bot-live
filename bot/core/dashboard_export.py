"""Exporte un fichier dashboard_data.js que le dashboard HTML peut charger en file://.

Permet de visualiser le dashboard en double-clic sans serveur (contourne les CORS file://).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def export_dashboard_data(bot_keys: Iterable[str], data_dir: str, dashboard_dir: str) -> str:
    bots_payload = []
    for key in bot_keys:
        bot_entry = {"key": key, "name": key.replace("_", " ").title()}
        for kind, suffix in [("state", "_state.json"), ("equity_curve", "_equity.json"), ("heartbeat", None)]:
            if kind == "heartbeat":
                fname = f"heartbeat_{key}.json"
            else:
                fname = key + suffix
            path = Path(data_dir) / fname
            if path.exists():
                try:
                    bot_entry[kind] = json.loads(path.read_text())
                except Exception:
                    bot_entry[kind] = None
        bots_payload.append(bot_entry)

    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bots": bots_payload,
    }
    out_path = Path(dashboard_dir) / "dashboard_data.js"
    js_content = "window.BOT_DATA = " + json.dumps(payload, indent=2, default=str) + ";\n"
    out_path.write_text(js_content)
    return str(out_path)


if __name__ == "__main__":
    here = Path(__file__).resolve().parents[2]
    out = export_dashboard_data(
        bot_keys=["sentiment_v1"],
        data_dir=str(here / "data"),
        dashboard_dir=str(here / "dashboard"),
    )
    print(f"Wrote {out}")
