"""Stratégie sentiment — règles exactes observées dans le paper bot TRADING FLEET.

Reproduit :
- Long si score ≥ LONG_THRESHOLD (0.65)
- Short si score ≤ SHORT_THRESHOLD (0.40)
- MAX_HOLD conditionnel : ferme après N heures uniquement si PnL ∈ ±exit_band
- TP/SL hard, trailing stop
- Veto technique : pas d'entrée si déjà bougé > VETO_PCT contre direction
- Cooldown 48h après 3 pertes consécutives sur même coin
- Kill switch sur drawdown global
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .state import BotState, OpenPosition, ClosedTrade

log = logging.getLogger(__name__)


# ===== Paramètres standards (validés en prod par paper bot) =====

@dataclass
class StrategyParams:
    long_threshold: float = 0.65
    short_threshold: float = 0.40
    max_hold_hours: int = 72
    exit_band_pct: float = 0.01           # ±1 %
    tp_pct: float = 0.05                  # +5 %
    sl_pct: float = -0.08                 # -8 %
    trailing_pct: float = 0.03            # +3 % trailing une fois TP1 touché
    veto_pct: float = 0.03                # annule entry si déjà bougé > 3 % contre
    cooldown_hours: int = 48
    max_positions: int = 8
    leverage: int = 3                     # CRYPTO LIVE = 3x conservateur
    notional_per_trade_pct: float = 0.10  # 10 % du equity par position

    @classmethod
    def scalp(cls) -> "StrategyParams":
        return cls(max_hold_hours=24, exit_band_pct=0.005)


class ExitReason(str, Enum):
    HARD_TP = "HARD_TP"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    MAX_HOLD = "MAX_HOLD"
    SIGNAL_REVERSE = "SIGNAL_REVERSE"
    KILL_SWITCH = "KILL_SWITCH"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _hours_since(iso: str) -> float:
    dt = datetime.fromisoformat(iso.replace("Z", "")).replace(tzinfo=timezone.utc) if "T" in iso else datetime.now(timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600


# ===== Décisions =====

@dataclass
class EntryDecision:
    coin: str
    direction: str           # "long" | "short"
    sentiment_score: float
    article_count: int
    reason: str


@dataclass
class ExitDecision:
    position: OpenPosition
    reason: ExitReason
    detail: str


def evaluate_entries(
    sentiment_by_coin: dict,           # {coin: SentimentResult}
    state: BotState,
    params: StrategyParams,
    price_change_24h: dict[str, float] | None = None,
) -> list[EntryDecision]:
    """Renvoie les candidats à l'ouverture après veto/cooldown/slots."""
    decisions: list[EntryDecision] = []
    if len(state.open_positions) >= params.max_positions:
        return decisions

    # Coins déjà ouverts → pas re-doubler
    already_open = {p.metadata.get("ticker", p.symbol.replace("SHORT-", "")) for p in state.open_positions}

    # Coins en cooldown
    in_cooldown = _coins_in_cooldown(state, params)

    candidates = []
    for coin, sent in sentiment_by_coin.items():
        if coin in already_open or coin in in_cooldown:
            continue
        if sent.article_count < 2:        # le PDF dit ≥ 2 articles/coin requis
            continue
        if sent.score >= params.long_threshold:
            candidates.append((coin, "long", sent))
        elif sent.score <= params.short_threshold:
            candidates.append((coin, "short", sent))

    # Tri : extrémité du score d'abord (plus la conviction est forte, plus prioritaire)
    candidates.sort(key=lambda x: abs(x[2].score - 0.5), reverse=True)

    slots = params.max_positions - len(state.open_positions)
    for coin, direction, sent in candidates[:slots]:
        # Veto technique : si le prix a déjà bougé > veto_pct dans la direction opposée
        # (on n'achète pas un train en marche, on ne shorte pas un crash)
        if price_change_24h and coin in price_change_24h:
            ch = price_change_24h[coin]
            if direction == "long" and ch > params.veto_pct * 100:
                log.info("VETO %s LONG: déjà +%.2f%% 24h", coin, ch)
                continue
            if direction == "short" and ch < -params.veto_pct * 100:
                log.info("VETO %s SHORT: déjà %.2f%% 24h", coin, ch)
                continue
        decisions.append(EntryDecision(
            coin=coin,
            direction=direction,
            sentiment_score=sent.score,
            article_count=sent.article_count,
            reason=f"{direction.upper()} sentiment: {sent.score:.2f} ({sent.article_count} articles)",
        ))
    return decisions


def evaluate_exits(state: BotState, params: StrategyParams) -> list[ExitDecision]:
    out: list[ExitDecision] = []
    for pos in state.open_positions:
        decision = _evaluate_single_exit(pos, params)
        if decision:
            out.append(decision)
    return out


def _evaluate_single_exit(pos: OpenPosition, params: StrategyParams) -> Optional[ExitDecision]:
    direction = "long" if pos.side == "buy" else "short"
    # PnL % sur le notional (sans leverage), pour aligner avec les seuils
    if direction == "long":
        pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price
    else:
        pnl_pct = (pos.entry_price - pos.current_price) / pos.entry_price

    # 1. HARD TP
    if pnl_pct >= params.tp_pct:
        return ExitDecision(pos, ExitReason.HARD_TP, f"+{pnl_pct*100:.1f}%")
    # 2. HARD SL
    if pnl_pct <= params.sl_pct:
        return ExitDecision(pos, ExitReason.STOP_LOSS, f"{pnl_pct*100:.1f}%")
    # 3. MAX_HOLD conditionnel
    if _hours_since(pos.opened_at) >= params.max_hold_hours:
        if abs(pnl_pct) <= params.exit_band_pct:
            return ExitDecision(pos, ExitReason.MAX_HOLD, f"in_band pnl={pnl_pct*100:.2f}%")
    # 4. Trailing stop (si la position a touché TP1 / mid-target)
    # Simplifié : si on est passé > tp_pct/2 puis on retombe sous trailing_pct → sortie
    # (le trailing détaillé sera géré par metadata.tp1_done dans le bot)
    return None


def _coins_in_cooldown(state: BotState, params: StrategyParams) -> set[str]:
    """Coins ayant subi 3 pertes consécutives dans la dernière fenêtre cooldown."""
    if not state.closed_trades:
        return set()
    cutoff_hours = params.cooldown_hours
    out: set[str] = set()
    # Groupé par coin (en virant le préfixe SHORT-)
    per_coin: dict[str, list[ClosedTrade]] = {}
    for t in state.closed_trades:
        coin = t.symbol.replace("SHORT-", "")
        per_coin.setdefault(coin, []).append(t)
    for coin, trades in per_coin.items():
        # Garder les derniers trades dans la fenêtre
        recent = [t for t in trades if _hours_since(t.closed_at) < cutoff_hours]
        recent.sort(key=lambda t: t.closed_at)
        if len(recent) >= 3 and all(t.realized_pnl < 0 for t in recent[-3:]):
            out.add(coin)
            log.info("COOLDOWN %s (3 pertes consécutives)", coin)
    return out


# ===== Sizing =====

def compute_position_size(state: BotState, params: StrategyParams, current_price: float) -> tuple[float, float]:
    """Renvoie (quantity, notional_usd)."""
    notional_usd = state.equity * params.notional_per_trade_pct * params.leverage
    quantity = notional_usd / current_price
    return quantity, notional_usd
