"""Exporte un fichier dashboard_data.js que le dashboard HTML peut charger en file://.

Permet de visualiser le dashboard en double-clic sans serveur (contourne les CORS file://).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


# Mapping noms + couleurs identiques à la flotte Zahid observée dans la vidéo 2026-05-15
BOT_DISPLAY = {
    "sentiment_ls_v3":    {"name": "LS V3",       "color": "#eab308"},  # yellow
    "ultimate_v2":        {"name": "Ultimate V2", "color": "#8b5cf6"},  # purple
    "sentiment_ls_v3_tp": {"name": "LS V3 TP",    "color": "#ca8a04"},  # amber
    "confluence":         {"name": "CONFLUENCE",  "color": "#16a34a"},  # green
    "forex_v1":           {"name": "FOREX V1",    "color": "#0ea5e9"},  # sky
    "tsla_v1":            {"name": "TESLA",       "color": "#e11d48"},  # rose
    "pltr_v1":            {"name": "PALANTIR",    "color": "#06b6d4"},  # cyan
    "amd_v1":             {"name": "AMD",         "color": "#84cc16"},  # lime
    "sentiment_v1":       {"name": "Sentiment V1","color": "#22d3ee"},  # cyan-bright
}


def export_dashboard_data(bot_keys: Iterable[str], data_dir: str, dashboard_dir: str) -> str:
    bots_payload = []
    for key in bot_keys:
        meta = BOT_DISPLAY.get(key, {"name": key.replace("_", " ").title(), "color": "#22d3ee"})
        bot_entry = {"key": key, "name": meta["name"], "color": meta["color"]}
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
