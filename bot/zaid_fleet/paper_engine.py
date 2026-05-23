"""
PaperTrader engine — shared foundation for all 4 paper trading bots.

Provides:
- PaperTrader class with full position management, stats, persistence
- CoinGecko / Binance price fetching with retry logic
- Atomic JSON I/O
- Telegram notifications
"""

import json
import os
import time
import math
import uuid
import traceback
import requests
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

from paper_config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT,
    MAX_LOG_ENTRIES,
    MAX_EQUITY_POINTS,
)

# ---------------------------------------------------------------------------
# Directory — state files live in CRYPTO_BOT_LIVE/data/ (shared with fleet)
# Override via PAPER_DATA_DIR env var if needed.
# ---------------------------------------------------------------------------
_default_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
BASE_DIR = Path(os.environ.get("PAPER_DATA_DIR", str(_default_data_dir)))
BASE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# HTTP session with CoinGecko-friendly headers
# ---------------------------------------------------------------------------
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "PaperTradingBot/1.0 (educational; contact@example.com)",
    "Accept": "application/json",
})
_RETRY_WAIT = 30  # seconds to wait on 429


# ===================================================================
#  UTILITY FUNCTIONS
# ===================================================================

def safe_json_write(filepath: str, data) -> None:
    """Atomic JSON write with retry for Windows file locking."""
    filepath = str(filepath)
    tmp = filepath + ".tmp"
    for attempt in range(3):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
            os.replace(tmp, filepath)
            return
        except PermissionError:
            time.sleep(0.5 * (attempt + 1))
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
    # Last attempt — direct write (no atomic)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except Exception:
        pass


def safe_json_read(filepath: str, fallback=None):
    """Read JSON with fallback on corruption or missing file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback if fallback is not None else {}


def _api_get(url: str, params: dict = None, timeout: int = 15):
    """GET with single retry on 429."""
    for attempt in range(2):
        try:
            r = _SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                if attempt == 0:
                    time.sleep(_RETRY_WAIT)
                    continue
                r.raise_for_status()
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == 0:
                time.sleep(2)
                continue
            raise
    return None


def fetch_price_coingecko(coin_id: str) -> float:
    """Fetch a single coin price from CoinGecko (USD)."""
    data = _api_get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": coin_id, "vs_currencies": "usd"},
    )
    return float(data[coin_id]["usd"])


def fetch_prices_coingecko(coin_ids: list) -> dict:
    """Fetch multiple coin prices from CoinGecko. Returns {coin_id: price}."""
    ids_str = ",".join(coin_ids)
    data = _api_get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": ids_str, "vs_currencies": "usd"},
    )
    return {cid: float(data[cid]["usd"]) for cid in coin_ids if cid in data}


def fetch_btc_klines_binance(interval: str = "5m", limit: int = 12) -> list:
    """
    Fetch BTC/USDT klines from Binance.
    Returns list of dicts: {open, high, low, close, volume, ts}.
    """
    data = _api_get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": "BTCUSDT", "interval": interval, "limit": limit},
    )
    result = []
    for k in data:
        result.append({
            "ts": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })
    return result


def fetch_categories_coingecko() -> list:
    """Fetch CoinGecko category list with market data."""
    return _api_get("https://api.coingecko.com/api/v3/coins/categories") or []


def fetch_markets_coingecko(per_page: int = 50) -> list:
    """Fetch top coins by market cap from CoinGecko."""
    return _api_get(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": 1,
            "sparkline": "false",
        },
    ) or []


def send_telegram(msg: str) -> bool:
    """DISABLED — Telegram is handled ONLY by watchdog_multi.py on realized profit."""
    return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _now_epoch() -> int:
    return int(time.time())


# ===================================================================
#  PAPER TRADER CLASS
# ===================================================================

class PaperTrader:
    """
    Simulated trading engine with full position tracking, stats, and persistence.
    Each bot gets its own instance with separate state/log/equity files.
    """

    def __init__(
        self,
        bot_id: str,
        initial_capital: float,
        state_file: str,
        log_file: str,
        equity_file: str,
        heartbeat_file: str,
        fee_bps: int = 10,
        slippage_bps: int = 10,
        leverage: float = 1.0,
    ):
        self.bot_id = bot_id
        self.initial_capital = initial_capital
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.leverage = max(1.0, float(leverage))

        # File paths (relative to BASE_DIR)
        self.state_path = str(BASE_DIR / state_file)
        self.log_path = str(BASE_DIR / log_file)
        self.equity_path = str(BASE_DIR / equity_file)
        self.heartbeat_path = str(BASE_DIR / heartbeat_file)

        # Core state
        self.cash: float = initial_capital
        self.equity: float = initial_capital
        self.peak_equity: float = initial_capital
        self.open_positions: list = []
        self.closed_trades: list = []
        self.total_trades: int = 0
        self.total_fees: float = 0.0
        self.started_at: str = _now_iso()
        self.last_cycle: str = _now_iso()
        self.cycle_count: int = 0
        self.custom: dict = {}

        # Internal counter for position IDs
        self._position_counter: int = 0

        # Try to restore previous state
        self.load_state()

    # ------------------------------------------------------------------
    #  TRADING
    # ------------------------------------------------------------------

    def buy(
        self,
        symbol: str,
        amount_usd: float,
        price: float,
        reason: str = "",
        metadata: dict = None,
    ) -> dict | None:
        """
        Simulate a buy order with slippage and fees.
        Returns the position dict, or None if insufficient cash.
        """
        if amount_usd <= 0 or price <= 0:
            self.append_log("WARN", f"Invalid buy params: amount={amount_usd}, price={price}")
            return None

        # Apply slippage (worse price for buyer = higher)
        slippage_mult = 1 + (self.slippage_bps / 10_000)
        exec_price = price * slippage_mult

        # Calculate fee
        fee = amount_usd * (self.fee_bps / 10_000)
        total_cost = amount_usd + fee

        # Margin = notional / leverage. Fee is always paid up-front.
        margin_required = (amount_usd / self.leverage) + fee

        if margin_required > self.cash:
            self.append_log("WARN", f"Insufficient margin for {symbol}: need ${margin_required:.2f}, have ${self.cash:.2f} (lev x{self.leverage:.0f})")
            return None

        # Execute
        quantity = amount_usd / exec_price
        self._position_counter += 1
        pos_id = f"{self.bot_id.upper()}-{self._position_counter:04d}"

        position = {
            "id": pos_id,
            "symbol": symbol,
            "side": "buy",
            "entry_price": round(exec_price, 8),
            "current_price": round(exec_price, 8),
            "size_usd": round(amount_usd, 4),
            "quantity": round(quantity, 8),
            "unrealized_pnl": 0.0,
            "fee_paid": round(fee, 6),
            "margin_locked": round(margin_required - fee, 4),
            "leverage": self.leverage,
            "opened_at": _now_iso(),
            "reason": reason,
            "metadata": metadata or {},
        }

        self.cash -= margin_required
        self.total_fees += fee
        self.total_trades += 1
        self.open_positions.append(position)

        self._recalc_equity()
        self.append_log("BUY", f"{symbol} ${amount_usd:.2f} @ {exec_price:.6f} (fee ${fee:.4f})", {"position_id": pos_id, "reason": reason})

        return position

    def sell(self, position_id: str, price: float, reason: str = "") -> dict | None:
        """
        Close a position by its ID. Returns dict with realized PnL, or None if not found.
        """
        pos = None
        pos_idx = None
        for i, p in enumerate(self.open_positions):
            if p["id"] == position_id:
                pos = p
                pos_idx = i
                break

        if pos is None:
            self.append_log("WARN", f"Position {position_id} not found for sell")
            return None

        return self._close_position(pos_idx, price, reason)

    def sell_by_symbol(self, symbol: str, price: float, reason: str = "") -> dict | None:
        """
        Close the first open position matching symbol. Returns realized PnL dict or None.
        """
        for i, p in enumerate(self.open_positions):
            if p["symbol"] == symbol:
                return self._close_position(i, price, reason)

        self.append_log("WARN", f"No open position for {symbol}")
        return None

    def _close_position(self, pos_idx: int, price: float, reason: str) -> dict:
        """Internal: close position at index, apply slippage/fees, record trade."""
        pos = self.open_positions.pop(pos_idx)
        direction = pos.get("metadata", {}).get("direction", "long")

        # Slippage on sell (worse = lower price for longs, higher for shorts)
        if direction == "short":
            slippage_mult = 1 + (self.slippage_bps / 10_000)  # Worse = higher price to close short
        else:
            slippage_mult = 1 - (self.slippage_bps / 10_000)  # Worse = lower price to sell long
        exec_price = price * slippage_mult

        # Fee
        proceeds = pos["quantity"] * exec_price
        fee = proceeds * (self.fee_bps / 10_000)

        # PnL depends on direction
        cost_basis = pos["quantity"] * pos["entry_price"]
        # Release locked margin (fallback to size_usd for legacy positions opened before leverage support)
        margin_locked = pos.get("margin_locked", pos["size_usd"])
        if direction == "short":
            # Short: profit = (entry - exit) * quantity - fees
            realized_pnl = (cost_basis - proceeds) - fee
            self.cash += margin_locked + realized_pnl
        else:
            # Long: profit = (exit - entry) * quantity - fees
            net_proceeds = proceeds - fee
            realized_pnl = net_proceeds - cost_basis
            self.cash += margin_locked + realized_pnl

        pnl_pct = (realized_pnl / pos["size_usd"] * 100) if pos["size_usd"] > 0 else 0.0

        self.total_fees += fee
        self.total_fees += fee

        # Record closed trade
        trade = {
            "id": pos["id"],
            "symbol": pos["symbol"],
            "entry_price": pos["entry_price"],
            "exit_price": round(exec_price, 8),
            "quantity": pos["quantity"],
            "size_usd": pos["size_usd"],
            "realized_pnl": round(realized_pnl, 4),
            "pnl_pct": round(pnl_pct, 2),
            "fee_entry": pos["fee_paid"],
            "fee_exit": round(fee, 6),
            "total_fees": round(pos["fee_paid"] + fee, 6),
            "opened_at": pos["opened_at"],
            "closed_at": _now_iso(),
            "hold_reason": pos["reason"],
            "close_reason": reason,
        }

        self.closed_trades.append(trade)
        # Keep only last 100 closed trades in memory
        if len(self.closed_trades) > 100:
            self.closed_trades = self.closed_trades[-100:]

        self._recalc_equity()
        self.append_log(
            "SELL",
            f"{pos['symbol']} @ {exec_price:.6f} PnL ${realized_pnl:+.2f} ({pnl_pct:+.1f}%)",
            {"position_id": pos["id"], "realized_pnl": realized_pnl, "reason": reason},
        )

        return trade

    def partial_close(self, position_id: str, pct: float, price: float, reason: str = "") -> dict | None:
        """Close `pct` of a position (0 < pct < 1). Reduces quantity/size/margin in place
        and records a closed_trade for the partial. Returns the partial trade dict or None.
        Used for TP1_PARTIAL / TP2_PARTIAL (style Confluence)."""
        if not (0 < pct < 1):
            return None
        pos = next((p for p in self.open_positions if p["id"] == position_id), None)
        if pos is None:
            return None

        direction = pos.get("metadata", {}).get("direction", "long")
        slip = (self.slippage_bps / 10_000)
        exec_price = price * (1 + slip) if direction == "short" else price * (1 - slip)

        qty_close = pos["quantity"] * pct
        size_close = pos["size_usd"] * pct
        margin_close = pos.get("margin_locked", pos["size_usd"]) * pct

        cost_basis = qty_close * pos["entry_price"]
        proceeds = qty_close * exec_price
        fee = proceeds * (self.fee_bps / 10_000)

        if direction == "short":
            realized_pnl = (cost_basis - proceeds) - fee
        else:
            realized_pnl = (proceeds - fee) - cost_basis

        pnl_pct = (realized_pnl / size_close * 100) if size_close > 0 else 0.0

        self.cash += margin_close + realized_pnl
        self.total_fees += fee

        # Shrink the open position
        pos["quantity"] -= qty_close
        pos["size_usd"] -= size_close
        if "margin_locked" in pos:
            pos["margin_locked"] -= margin_close

        trade = {
            "id": pos["id"] + f"-p{int(pct*100)}",
            "symbol": pos["symbol"],
            "entry_price": pos["entry_price"],
            "exit_price": round(exec_price, 8),
            "quantity": round(qty_close, 8),
            "size_usd": round(size_close, 4),
            "realized_pnl": round(realized_pnl, 4),
            "pnl_pct": round(pnl_pct, 2),
            "fee_entry": 0.0,
            "fee_exit": round(fee, 6),
            "total_fees": round(fee, 6),
            "opened_at": pos["opened_at"],
            "closed_at": _now_iso(),
            "hold_reason": pos.get("reason", ""),
            "close_reason": reason,
            "partial_pct": pct,
        }
        self.closed_trades.append(trade)
        if len(self.closed_trades) > 100:
            self.closed_trades = self.closed_trades[-100:]

        self._recalc_equity()
        self.append_log(
            "PARTIAL_SELL",
            f"{pos['symbol']} {int(pct*100)}% @ {exec_price:.6f} PnL ${realized_pnl:+.2f} ({pnl_pct:+.1f}%)",
            {"position_id": pos["id"], "realized_pnl": realized_pnl, "reason": reason, "pct": pct},
        )
        return trade

    # ------------------------------------------------------------------
    #  PRICE UPDATES & EQUITY
    # ------------------------------------------------------------------

    def update_prices(self, prices: dict) -> None:
        """
        Update current_price and unrealized_pnl for all open positions.
        prices: {symbol: current_price}
        """
        for pos in self.open_positions:
            if pos["symbol"] in prices:
                new_price = prices[pos["symbol"]]
                pos["current_price"] = round(new_price, 8)
                cost = pos["quantity"] * pos["entry_price"]
                value = pos["quantity"] * new_price
                pos["unrealized_pnl"] = round(value - cost, 4)

        self._recalc_equity()

    def _recalc_equity(self) -> None:
        """Recalculate total equity and update peak. Handles shorts correctly."""
        total_value = 0
        for p in self.open_positions:
            direction = p.get("metadata", {}).get("direction", "long")
            margin_locked = p.get("margin_locked", p["size_usd"])
            entry_val = p["quantity"] * p["entry_price"]
            current_val = p["quantity"] * p["current_price"]
            if direction == "short":
                unrealized = entry_val - current_val
            else:
                unrealized = current_val - entry_val
            # Position equity contribution = margin held + mark-to-market PnL
            total_value += margin_locked + unrealized
        self.equity = round(self.cash + total_value, 4)
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

    def get_equity(self) -> float:
        """Return current equity: cash + market value of all open positions."""
        self._recalc_equity()
        return self.equity

    def get_drawdown(self) -> float:
        """Return current drawdown from peak as a positive percentage."""
        if self.peak_equity <= 0:
            return 0.0
        dd = (self.peak_equity - self.equity) / self.peak_equity * 100
        return round(max(dd, 0.0), 2)

    # ------------------------------------------------------------------
    #  STATS
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """
        Compute trading statistics from closed trades.
        Returns dict with win_rate, total_trades, avg_pnl, profit_factor,
        sharpe, total_fees, best_trade, worst_trade.
        """
        trades = self.closed_trades
        n = len(trades)

        if n == 0:
            return {
                "win_rate": 0.0,
                "total_trades": self.total_trades,
                "closed_trades": 0,
                "avg_pnl": 0.0,
                "profit_factor": 0.0,
                "sharpe": 0.0,
                "total_fees": round(self.total_fees, 4),
                "best_trade": 0.0,
                "worst_trade": 0.0,
            }

        pnls = [t["realized_pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate = (len(wins) / n * 100) if n > 0 else 0.0
        avg_pnl = sum(pnls) / n

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        # Sharpe from equity curve (daily returns)
        sharpe = self._calc_sharpe()

        return {
            "win_rate": round(win_rate, 1),
            "total_trades": self.total_trades,
            "closed_trades": n,
            "avg_pnl": round(avg_pnl, 4),
            "profit_factor": round(profit_factor, 2),
            "sharpe": round(sharpe, 2),
            "total_fees": round(self.total_fees, 4),
            "best_trade": round(max(pnls), 4),
            "worst_trade": round(min(pnls), 4),
        }

    def _calc_sharpe(self) -> float:
        """Calculate annualized Sharpe ratio from equity points (grouped by day)."""
        equity_data = safe_json_read(self.equity_path, fallback=[])
        if not isinstance(equity_data, list) or len(equity_data) < 2:
            return 0.0

        # Group equity by day, take last value per day
        daily = {}
        for pt in equity_data:
            day = pt.get("ts", "")[:10]  # YYYY-MM-DD
            if day:
                daily[day] = pt.get("equity", 0)

        days_sorted = sorted(daily.keys())
        if len(days_sorted) < 2:
            return 0.0

        # Daily returns
        returns = []
        for i in range(1, len(days_sorted)):
            prev = daily[days_sorted[i - 1]]
            curr = daily[days_sorted[i]]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if len(returns) < 2:
            return 0.0

        avg_ret = sum(returns) / len(returns)
        std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in returns) / (len(returns) - 1))

        if std_ret == 0:
            return 0.0

        # Annualize: sqrt(365) for crypto
        return (avg_ret / std_ret) * math.sqrt(365)

    # ------------------------------------------------------------------
    #  PERSISTENCE
    # ------------------------------------------------------------------

    def save_state(self) -> None:
        """Persist full state to JSON (atomic write)."""
        state = {
            "bot_id": self.bot_id,
            "cash": round(self.cash, 4),
            "equity": round(self.equity, 4),
            "peak_equity": round(self.peak_equity, 4),
            "initial_capital": self.initial_capital,
            "open_positions": self.open_positions,
            "closed_trades": self.closed_trades,
            "total_trades": self.total_trades,
            "total_fees": round(self.total_fees, 6),
            "started_at": self.started_at,
            "last_cycle": self.last_cycle,
            "cycle_count": self.cycle_count,
            "custom": self.custom,
            "_position_counter": self._position_counter,
            "_saved_at": _now_iso(),
        }
        safe_json_write(self.state_path, state)

    def load_state(self) -> bool:
        """Restore state from JSON. Returns True if state was loaded."""
        state = safe_json_read(self.state_path, fallback=None)
        if state is None:
            return False

        try:
            # FIX 2026-05-02: hydrate initial_capital from state if present
            self.initial_capital = float(state.get("initial_capital", self.initial_capital))
            self.cash = float(state.get("cash", self.initial_capital))
            self.equity = float(state.get("equity", self.initial_capital))
            self.peak_equity = float(state.get("peak_equity", self.initial_capital))
            self.open_positions = state.get("open_positions", [])
            self.closed_trades = state.get("closed_trades", [])
            self.total_trades = int(state.get("total_trades", 0))
            self.total_fees = float(state.get("total_fees", 0.0))
            self.started_at = state.get("started_at", self.started_at)
            self.last_cycle = state.get("last_cycle", self.last_cycle)
            self.cycle_count = int(state.get("cycle_count", 0))
            self.custom = state.get("custom", {})
            self._position_counter = int(state.get("_position_counter", 0))
            self._recalc_equity()
            return True
        except (ValueError, TypeError, KeyError) as e:
            self.append_log("ERROR", f"Failed to load state: {e}")
            return False

    def write_heartbeat(self, status: str = "running") -> None:
        """Write heartbeat file with PID, timestamp, and status."""
        safe_json_write(self.heartbeat_path, {
            "pid": os.getpid(),
            "ts": _now_epoch(),
            "ts_iso": _now_iso(),
            "status": status,
            "bot_id": self.bot_id,
            "cycle_count": self.cycle_count,
            "equity": round(self.equity, 2),
        })

    # ------------------------------------------------------------------
    #  LOGGING
    # ------------------------------------------------------------------

    def append_log(self, level: str, msg: str, data: dict = None) -> None:
        """Append a structured log entry. Capped at MAX_LOG_ENTRIES."""
        logs = safe_json_read(self.log_path, fallback=[])
        if not isinstance(logs, list):
            logs = []

        entry = {
            "ts": _now_iso(),
            "level": level,
            "bot": self.bot_id,
            "msg": msg,
        }
        if data:
            entry["data"] = data

        logs.append(entry)

        # Cap size
        if len(logs) > MAX_LOG_ENTRIES:
            logs = logs[-MAX_LOG_ENTRIES:]

        safe_json_write(self.log_path, logs)

    # ------------------------------------------------------------------
    #  EQUITY CURVE
    # ------------------------------------------------------------------

    def append_equity_point(self) -> None:
        """Append current equity snapshot to the equity curve file."""
        self._recalc_equity()
        invested = sum(p["quantity"] * p["current_price"] for p in self.open_positions)

        points = safe_json_read(self.equity_path, fallback=[])
        if not isinstance(points, list):
            points = []

        points.append({
            "ts": _now_iso(),
            "equity": round(self.equity, 4),
            "cash": round(self.cash, 4),
            "invested": round(invested, 4),
            "dd": self.get_drawdown(),
        })

        # Cap size
        if len(points) > MAX_EQUITY_POINTS:
            points = points[-MAX_EQUITY_POINTS:]

        safe_json_write(self.equity_path, points)

    # ------------------------------------------------------------------
    #  EXPORT
    # ------------------------------------------------------------------

    def export_state(self) -> dict:
        """Full state dict for dashboard consumption."""
        self._recalc_equity()
        stats = self.get_stats()
        invested = sum(p["quantity"] * p["current_price"] for p in self.open_positions)
        total_pnl = self.equity - self.initial_capital

        return {
            "bot_id": self.bot_id,
            "cash": round(self.cash, 4),
            "equity": round(self.equity, 4),
            "initial_capital": self.initial_capital,
            "total_pnl": round(total_pnl, 4),
            "total_pnl_pct": round((total_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0, 2),
            "peak_equity": round(self.peak_equity, 4),
            "drawdown": self.get_drawdown(),
            "invested": round(invested, 4),
            "open_positions": self.open_positions,
            "num_open": len(self.open_positions),
            "closed_trades": self.closed_trades[-20:],  # Last 20 for dashboard
            "stats": stats,
            "started_at": self.started_at,
            "last_cycle": self.last_cycle,
            "cycle_count": self.cycle_count,
            "custom": self.custom,
        }

    # ------------------------------------------------------------------
    #  CYCLE HELPER
    # ------------------------------------------------------------------

    def tick(self) -> None:
        """Call at the start of each bot cycle to update counters and heartbeat."""
        self.cycle_count += 1
        self.last_cycle = _now_iso()
        self.write_heartbeat("running")
