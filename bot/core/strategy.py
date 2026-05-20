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
    """Paramètres validés par PDF Sentiment Cartography + système Zahid 15 mai."""
    # Seuils sentiment (PDF planche III)
    long_threshold: float = 0.65          # ≥ 0.65 → LONG
    short_threshold: float = 0.40         # ≤ 0.40 → SHORT
    # Article minimum par coin (assoupli à 1 pour avoir des trades avec RSS publics limités)
    min_articles_per_coin: int = 1
    # MAX_HOLD conditionnel (Zahid 15 mai)
    max_hold_hours: int = 72              # 72h pour bots standard
    hold_minimal_hours: int = 24          # PDF planche VIII : hold minimal 24h
    exit_band_pct: float = 0.01           # ferme dans ±1 % après MAX_HOLD
    # ⭐ RATIO 3:1 — méthode Zahid vidéo 20 avril 13:00-14:30
    # "Je me prends mes profits à 3%. Quand je perds, je perds max 1%."
    # Avec ce ratio, même 40% WR = RENTABLE
    tp1_pct: float = 0.01                 # +1% → ferme 1/3
    tp2_pct: float = 0.02                 # +2% → ferme 1/3 supplémentaire
    tp_pct: float = 0.03                  # +3% → ferme le reste (HARD TP)
    sl_pct: float = -0.01                 # -1% SL (max perte par trade)
    trailing_pct: float = 0.005           # trailing 0.5% après TP1
    # Garde-fous (PDF planche VI)
    veto_pct: float = 0.03                # ±3 % move contre = annule
    cooldown_hours: int = 48              # 48h après 3 pertes consécutives
    # Capital + positions
    max_positions: int = 8                # PDF planche VIII : max 8
    leverage: int = 3                     # CRYPTO LIVE 3x (PDF disait 10x paper, on est conservateur)
    notional_per_trade_pct: float = 0.10  # 10 % equity par position
    reserve_liquidity_pct: float = 0.10   # PDF planche VIII : 10 % réserve liquidité
    # Cycles
    cycle_minutes: int = 240              # PDF planche IV : cycle 4h
    # Coûts (PDF planche IV)
    slippage_bps: int = 2                 # 2 bps slippage simulé
    fee_bps: int = 2                      # 2 bps fee Hyperliquid maker

    @classmethod
    def scalp(cls) -> "StrategyParams":
        return cls(max_hold_hours=24, exit_band_pct=0.005)


# ===== DÉTECTION RÉGIME DE MARCHÉ (Zahid 15 mai) =====

def detect_market_regime(btc_24h_change_pct: float, fear_greed_index: int | None = None) -> str:
    """Détecte le régime de marché : RISK_ON / RISK_OFF / NEUTRAL.

    Critères (heuristique simple, à raffiner) :
    - RISK_ON  : BTC > +3 % sur 24h OU F&G > 70
    - RISK_OFF : BTC < -3 % sur 24h OU F&G < 30
    - NEUTRAL  : entre les deux
    """
    if btc_24h_change_pct > 3 or (fear_greed_index is not None and fear_greed_index > 70):
        return "RISK_ON"
    if btc_24h_change_pct < -3 or (fear_greed_index is not None and fear_greed_index < 30):
        return "RISK_OFF"
    return "NEUTRAL"


class ExitReason(str, Enum):
    TP1 = "TP1_PARTIAL"            # +2% : ferme 1/3
    TP2 = "TP2_PARTIAL"            # +3.5% : ferme 1/3 de plus
    HARD_TP = "HARD_TP"            # +5% : ferme le restant
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
    if direction == "long":
        pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price
    else:
        pnl_pct = (pos.entry_price - pos.current_price) / pos.entry_price

    tp1_done = pos.metadata.get("tp1_done", False)
    tp2_done = pos.metadata.get("tp2_done", False)

    # 1. HARD TP (+5%) → ferme tout
    if pnl_pct >= params.tp_pct:
        return ExitDecision(pos, ExitReason.HARD_TP, f"+{pnl_pct*100:.1f}%")
    # 2. TP2 (+3.5%) — ferme 1/3 supplémentaire (à gérer comme partial dans base_bot)
    if not tp2_done and pnl_pct >= params.tp2_pct:
        return ExitDecision(pos, ExitReason.TP2, f"+{pnl_pct*100:.1f}% partial")
    # 3. TP1 (+2%) — ferme 1/3
    if not tp1_done and pnl_pct >= params.tp1_pct:
        return ExitDecision(pos, ExitReason.TP1, f"+{pnl_pct*100:.1f}% partial")
    # 4. TRAILING (après TP1) : si on retombe sous +trailing_pct depuis le peak
    if tp1_done:
        peak_pnl = pos.metadata.get("peak_pnl_pct", pnl_pct)
        if pnl_pct < peak_pnl - params.trailing_pct:
            return ExitDecision(pos, ExitReason.TRAILING_STOP, f"peak +{peak_pnl*100:.1f}% → {pnl_pct*100:.1f}%")
    # 5. SL
    if pnl_pct <= params.sl_pct:
        return ExitDecision(pos, ExitReason.STOP_LOSS, f"{pnl_pct*100:.1f}%")
    # 6. MAX_HOLD conditionnel
    if _hours_since(pos.opened_at) >= params.max_hold_hours:
        if abs(pnl_pct) <= params.exit_band_pct:
            return ExitDecision(pos, ExitReason.MAX_HOLD, f"in_band pnl={pnl_pct*100:.2f}%")
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
