"""Persistence state.json / equity.json / heartbeat — format identique au TRADING FLEET.

Schéma observé via rétro-engineering du dashboard live (2026-05-19).
Stockage local en dev, Google Cloud Storage en prod (Cloud Run).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Google Cloud Storage est optionnel (mode local pour dev)
try:
    from google.cloud import storage  # type: ignore
    _HAS_GCS = True
except ImportError:
    _HAS_GCS = False


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class OpenPosition:
    """Format crypto (compatible state.json paper bot existant)."""
    id: str
    symbol: str                     # ex: "LINK" ou "SHORT-LINK"
    side: str                       # "buy" pour long, "sell" pour short
    entry_price: float
    current_price: float
    size_usd: float
    quantity: float
    unrealized_pnl: float
    fee_paid: float
    margin_locked: float
    leverage: int
    opened_at: str
    reason: str                     # ex: "LONG sentiment: 0.72 (12 articles)"
    metadata: dict = field(default_factory=dict)


@dataclass
class ClosedTrade:
    """Format identique au paper bot."""
    id: str
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    size_usd: float
    realized_pnl: float
    pnl_pct: float
    fee_entry: float
    fee_exit: float
    total_fees: float
    opened_at: str
    closed_at: str
    hold_reason: str
    close_reason: str               # "STOP_LOSS (-8.1%)" / "SHORT_HARD_TP (+5.0%)" / "MAX_HOLD" / "TRAILING_STOP" / "SIGNAL_REVERSE"


@dataclass
class BotState:
    bot_id: str
    initial_capital: float = 0
    cash: float = 0
    equity: float = 0
    peak_equity: float = 0
    open_positions: list[OpenPosition] = field(default_factory=list)
    closed_trades: list[ClosedTrade] = field(default_factory=list)
    total_trades: int = 0
    total_fees: float = 0
    started_at: str = field(default_factory=_now)
    last_cycle: str = field(default_factory=_now)
    cycle_count: int = 0
    custom: dict = field(default_factory=dict)
    _position_counter: int = 0
    _saved_at: str = field(default_factory=_now)


class StateStore:
    """Persiste state.json / equity.json / heartbeat_<bot>.json.

    Local : écrit dans data/<bot_id>_state.json
    GCS  : écrit dans gs://<bucket>/<prefix><bot_id>_state.json
    """

    def __init__(self, bot_id: str, local_dir: str = "data", gcs_bucket: Optional[str] = None, gcs_prefix: str = "data/"):
        self.bot_id = bot_id
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.gcs_bucket = gcs_bucket
        self.gcs_prefix = gcs_prefix
        self._gcs_client: Optional["storage.Client"] = None
        if gcs_bucket and _HAS_GCS:
            self._gcs_client = storage.Client()

    @property
    def state_file(self) -> str:
        return f"{self.bot_id}_state.json"

    @property
    def equity_file(self) -> str:
        return f"{self.bot_id}_equity.json"

    @property
    def heartbeat_file(self) -> str:
        return f"heartbeat_{self.bot_id}.json"

    # ===== READ =====

    def load_state(self) -> BotState:
        data = self._read_json(self.state_file)
        if not data:
            return BotState(bot_id=self.bot_id)
        # Reconstruct dataclasses
        opens = [OpenPosition(**p) for p in data.pop("open_positions", [])]
        closes = [ClosedTrade(**t) for t in data.pop("closed_trades", [])]
        return BotState(open_positions=opens, closed_trades=closes, **{k: v for k, v in data.items() if k in BotState.__dataclass_fields__})

    def load_equity_curve(self) -> list[list]:
        return self._read_json(self.equity_file) or []

    # ===== WRITE =====

    def save_state(self, state: BotState) -> None:
        state._saved_at = _now()
        d = asdict(state)
        self._write_json(self.state_file, d)

    def append_equity_point(self, equity: float) -> None:
        curve = self.load_equity_curve()
        curve.append([_now(), equity])
        curve = curve[-2000:]  # rolling window
        self._write_json(self.equity_file, curve)

    def heartbeat(self) -> None:
        self._write_json(self.heartbeat_file, {"ts": int(time.time()), "iso": _now()})

    # ===== I/O =====

    def _read_json(self, filename: str) -> Optional[dict | list]:
        if self._gcs_client and self.gcs_bucket:
            blob = self._gcs_client.bucket(self.gcs_bucket).blob(self.gcs_prefix + filename)
            if blob.exists():
                return json.loads(blob.download_as_text())
            return None
        path = self.local_dir / filename
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def _write_json(self, filename: str, data) -> None:
        text = json.dumps(data, indent=2, default=str)
        if self._gcs_client and self.gcs_bucket:
            blob = self._gcs_client.bucket(self.gcs_bucket).blob(self.gcs_prefix + filename)
            blob.upload_from_string(text, content_type="application/json")
            blob.cache_control = "no-cache, max-age=0"
            blob.patch()
        else:
            path = self.local_dir / filename
            path.write_text(text)


if __name__ == "__main__":
    # Smoke test
    store = StateStore("sentiment_v1", local_dir="/tmp/state_test")
    state = BotState(bot_id="sentiment_v1", initial_capital=2000, cash=2000, equity=2000, peak_equity=2000)
    store.save_state(state)
    store.append_equity_point(2000)
    store.heartbeat()
    loaded = store.load_state()
    print(f"OK saved+loaded: equity={loaded.equity}, bot={loaded.bot_id}")
