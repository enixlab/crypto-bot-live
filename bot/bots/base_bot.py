"""BaseBot — classe abstraite pour tous les bots de la flotte.

Reproduit la logique du paper bot : cycle 1) news pull, 2) sentiment scoring,
3) exits, 4) entries, 5) persist state.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from ..core.state import BotState, OpenPosition, ClosedTrade, StateStore
from ..core.strategy import StrategyParams, EntryDecision, ExitDecision, ExitReason, evaluate_entries, evaluate_exits, compute_position_size
from ..core.kill_switch import check_kill_switch, send_telegram_alert

# Hyperliquid SDK importé en lazy uniquement quand on est en live mode
if False:  # type-checking only
    from ..core.hyperliquid_client import HyperliquidClient

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class BaseBot(ABC):
    bot_id: str = "base"
    bot_name: str = "Base"

    def __init__(
        self,
        universe: list[str],
        params: StrategyParams,
        store: StateStore,
        hl_client=None,  # Optional[HyperliquidClient]
        paper_mode: bool = True,
    ):
        self.universe = universe
        self.params = params
        self.store = store
        self.hl = hl_client
        self.paper_mode = paper_mode
        self.state = store.load_state()
        if self.state.initial_capital == 0:
            self.state.initial_capital = float(__import__("os").environ.get("INITIAL_CAPITAL", "2000"))
            self.state.cash = self.state.initial_capital
            self.state.equity = self.state.initial_capital
            self.state.peak_equity = self.state.initial_capital

    @abstractmethod
    def fetch_signals(self) -> dict:
        """Renvoie {coin: SentimentResult}."""
        ...

    def cycle(self) -> None:
        """Un cycle complet du bot."""
        log.info("=== %s cycle %s ===", self.bot_id, self.state.cycle_count + 1)
        self.state.cycle_count += 1
        self.state.last_cycle = _now()

        # 1. Mark-to-market des positions existantes
        self._mark_to_market()

        # 2. Kill switch global
        if check_kill_switch(self.state, float(__import__("os").environ.get("KILL_SWITCH_DD_PCT", "-0.15"))):
            self._emergency_close_all()
            send_telegram_alert(f"🚨 *KILL SWITCH* — bot `{self.bot_id}` arrêté. Equity={self.state.equity:.0f} / Peak={self.state.peak_equity:.0f}")
            self.store.save_state(self.state)
            return

        # 3. Exits (TP/SL/MAX_HOLD)
        exits = evaluate_exits(self.state, self.params)
        for exit in exits:
            self._close_position(exit.position, exit.reason, exit.detail)

        # 4. Signaux
        sentiment_by_coin = self.fetch_signals()
        log.info("Sentiment scores: %s", {c: f"{r.score:.2f}({r.article_count})" for c, r in sentiment_by_coin.items()})

        # 5. Entries
        entries = evaluate_entries(sentiment_by_coin, self.state, self.params)
        for entry in entries:
            self._open_position(entry)

        # 6. Persist
        self.state.equity = self._compute_equity()
        if self.state.equity > self.state.peak_equity:
            self.state.peak_equity = self.state.equity
        self.store.save_state(self.state)
        self.store.append_equity_point(self.state.equity)
        self.store.heartbeat()

    # ===== HELPERS =====

    def _mark_to_market(self) -> None:
        for pos in self.state.open_positions:
            coin = pos.metadata.get("ticker", pos.symbol.replace("SHORT-", ""))
            price = self._get_price(coin)
            if price > 0:
                pos.current_price = price
                direction_mult = 1 if pos.side == "buy" else -1
                pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.quantity * direction_mult

    def _get_price(self, coin: str) -> float:
        if self.hl and not self.paper_mode:
            return self.hl.get_mark_price(coin)
        # Mode paper : prix simulé via API publique Hyperliquid (sans clé)
        try:
            import requests
            r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "allMids"}, timeout=10)
            mids = r.json()
            return float(mids.get(coin, 0))
        except Exception as e:
            log.warning("price fetch err %s: %s", coin, e)
            return 0

    def _compute_equity(self) -> float:
        unrealized = sum(p.unrealized_pnl for p in self.state.open_positions)
        return self.state.cash + sum(p.margin_locked for p in self.state.open_positions) + unrealized

    def _open_position(self, entry: EntryDecision) -> None:
        price = self._get_price(entry.coin)
        if price == 0:
            log.warning("price=0 pour %s, skip entry", entry.coin)
            return
        quantity, notional = compute_position_size(self.state, self.params, price)
        margin = notional / self.params.leverage
        if margin > self.state.cash:
            log.info("Cash insuffisant pour %s (need %.0f, have %.0f)", entry.coin, margin, self.state.cash)
            return

        fee = notional * 0.0002  # 2 bps maker fee Hyperliquid
        side = "buy" if entry.direction == "long" else "sell"
        symbol = entry.coin if entry.direction == "long" else f"SHORT-{entry.coin}"

        self.state._position_counter += 1
        pos = OpenPosition(
            id=f"{self.bot_id.upper()}-{self.state._position_counter:04d}",
            symbol=symbol,
            side=side,
            entry_price=price,
            current_price=price,
            size_usd=notional,
            quantity=quantity,
            unrealized_pnl=0,
            fee_paid=fee,
            margin_locked=margin,
            leverage=self.params.leverage,
            opened_at=_now(),
            reason=entry.reason,
            metadata={
                "ticker": entry.coin,
                "direction": entry.direction,
                "sentiment_score": entry.sentiment_score,
                "article_count": entry.article_count,
            },
        )

        # Exécution réelle si live mode
        if self.hl and not self.paper_mode:
            try:
                if entry.direction == "long":
                    res = self.hl.market_buy(entry.coin, quantity, self.params.leverage)
                else:
                    res = self.hl.market_sell(entry.coin, quantity, self.params.leverage)
                pos.metadata["hl_order"] = str(res)[:200]
            except Exception as e:
                log.error("HL order failed: %s", e)
                return

        self.state.cash -= (margin + fee)
        self.state.open_positions.append(pos)
        log.info("OPEN %s %s qty=%.4f @ %.4f notional=$%.0f", pos.symbol, side, quantity, price, notional)

    def _close_position(self, pos: OpenPosition, reason: ExitReason, detail: str) -> None:
        price = self._get_price(pos.metadata.get("ticker", pos.symbol.replace("SHORT-", "")))
        direction_mult = 1 if pos.side == "buy" else -1
        realized = (price - pos.entry_price) * pos.quantity * direction_mult
        fee_exit = pos.size_usd * 0.0002
        pnl_pct = (realized / pos.size_usd) * 100

        # Exécution réelle si live mode
        if self.hl and not self.paper_mode:
            try:
                coin = pos.metadata.get("ticker", pos.symbol.replace("SHORT-", ""))
                self.hl.close_position(coin)
            except Exception as e:
                log.error("HL close failed: %s", e)
                # On garde tout de même le state cohérent : on close en paper

        self.state.cash += pos.margin_locked + realized - fee_exit
        self.state.open_positions = [p for p in self.state.open_positions if p.id != pos.id]
        self.state.closed_trades.append(ClosedTrade(
            id=pos.id,
            symbol=pos.symbol,
            entry_price=pos.entry_price,
            exit_price=price,
            quantity=pos.quantity,
            size_usd=pos.size_usd,
            realized_pnl=realized,
            pnl_pct=pnl_pct,
            fee_entry=pos.fee_paid,
            fee_exit=fee_exit,
            total_fees=pos.fee_paid + fee_exit,
            opened_at=pos.opened_at,
            closed_at=_now(),
            hold_reason=pos.reason,
            close_reason=f"{reason.value} ({detail})",
        ))
        self.state.total_trades += 1
        self.state.total_fees += pos.fee_paid + fee_exit
        log.info("CLOSE %s [%s] pnl=$%.2f (%.2f%%)", pos.symbol, reason.value, realized, pnl_pct)

    def _emergency_close_all(self) -> None:
        for pos in list(self.state.open_positions):
            self._close_position(pos, ExitReason.KILL_SWITCH, "drawdown")
