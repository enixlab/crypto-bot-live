"""Entry point Cloud Run : expose un endpoint HTTP qui lance un cycle.

Cloud Scheduler → POST https://<service>.run.app/cycle → un cycle bot
"""
import os
import logging
from flask import Flask, jsonify, request

from bot.main import build_fleet

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health():
    return jsonify(ok=True, service="enix-crypto-bot")


@app.route("/cycle", methods=["POST", "GET"])
def cycle():
    mode = os.environ.get("BOT_MODE", "paper")
    network = os.environ.get("HYPERLIQUID_NETWORK", "testnet")
    gcs_bucket = os.environ.get("GCS_BUCKET")
    fleet = build_fleet(mode, network, gcs_bucket)
    results = []
    for bot in fleet:
        try:
            bot.cycle()
            results.append({"bot": bot.bot_id, "ok": True, "cycle": bot.state.cycle_count})
        except Exception as e:
            log.exception("bot %s err", bot.bot_id)
            results.append({"bot": bot.bot_id, "ok": False, "error": str(e)})
    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
