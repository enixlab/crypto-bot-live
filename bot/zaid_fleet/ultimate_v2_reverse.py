"""
ULTIMATE V2 REVERSE-ENGINEERED
==============================
Reproduction approximative de la strategie 'Ultimate V2' de Zaid
(PF 1.20, +14.9% sur 46 jours, 59 trades). Analysee 2026-05-23.

Caracteristiques observees chez Zaid :
- Triple signal a l'entree : sent + H + slope (conviction haute)
- LONG dominant (44L / 15S), WR LONG 64% / SHORT 40%
- "Trade rare mais sur" : 1.3 trades/jour
- Holding median 26.5h (P25=16h, P75=54h)
- Position size median ~$5,400, max ~$21,000 (gros sizing sur conviction)
- TP: hard 5% OU trailing apres profit (pas de TP partiel)
- SL fixe 8%
- SUI MASSACRE le bot (-$2,661 cumules) -> BLACKLIST SUI ici
- Aussi DOGE / FET / DOT a eviter
"""

import sys, os, time, traceback
from datetime import datetime, timezone
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

# Auto-load .env
for _c in (_here / ".env", _here.parent.parent / ".env"):
    if _c.exists():
        for _l in _c.read_text(encoding="utf-8").splitlines():
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
        break

from price_cache import get_cached_prices
from paper_engine import PaperTrader
from trade_filters import should_veto_entry, check_cooldown, update_cooldown_on_close, check_tp
from paper_config import BOT_CONFIGS
from sentiment_ls_v3_lo import (
    UNIVERSE, SYMBOL_MAP, collect_news, score_all_news,
    fetch_prices_cached, get_macro_regime,
    _local_check_blacklist, _local_update_blacklist,
)

# ============================================================
# ULTIMATE V2 PARAMS (deduits de 59 trades)
# ============================================================
REBALANCE_HOURS  = 6          # Plus rare que LS V3 (4h) et Confluence (2h)
MIN_HOLD_HOURS   = 16         # Holding long (P25 de Ultimate)
MAX_POSITIONS    = 4          # Conviction haute, peu de positions
CASH_RESERVE_PCT = 0.15       # Plus de cash en reserve (defensif)
STOP_LOSS_PCT    = 0.06       # Serre vs 8% (vu les massacres SUI)
TRAILING_SL_PCT  = 0.10
LEVERAGE         = 10

# Triple signal thresholds (conviction haute)
SENT_MIN         = 0.65       # Sentiment fort requis
H_MIN            = 0.60       # "Health" score (estime)
SLOPE_MIN        = 0.01       # Slope positif requis (>= +1% sur 24h)

# Blacklist (data Zaid)
BLACKLIST = {"SUI", "DOGE", "FET", "DOT"}  # SUI a fait perdre -$2,661 a Ultimate V2

def compute_health_score(coin, prices):
    """Score 'Health' base sur volume et stabilite de prix."""
    if coin not in prices:
        return 0.0
    px = prices[coin]
    chg = abs(px.get("change_24h", 0))
    vol = px.get("volume_24h", 0)
    import math
    # Volatilite moderee = sain (ni trop calme ni trop violent)
    vol_health = 1.0 - min(1.0, chg / 15.0)  # 0% = parfait, 15%+ = mauvais
    # Volume = liquidite
    vol_score = max(0.0, min(1.0, math.log10(max(vol, 1)) / 10.0))
    return 0.6 * vol_health + 0.4 * vol_score


class UltimateV2ReverseBot:

    def __init__(self, cfg):
        self.cfg = cfg
        self.trader = PaperTrader(
            bot_id="ultimate_v2_reverse",
            initial_capital=cfg["capital"],
            state_file="ultimate_v2_reverse_state.json",
            log_file="ultimate_v2_reverse_log.json",
            equity_file="ultimate_v2_reverse_equity.json",
            heartbeat_file="heartbeat_ultimate_v2_reverse.json",
            fee_bps=2, slippage_bps=2, leverage=LEVERAGE,
        )
        defaults = {"last_rebalance_ts": 0, "rebalance_count": 0,
                    "trailing_highs": {}, "trailing_lows": {}}
        for k, v in defaults.items():
            self.trader.custom.setdefault(k, v)

    def check_stops(self, prices):
        trailing = self.trader.custom.get("trailing_highs", {})
        trailing_lows = self.trader.custom.get("trailing_lows", {})
        to_close = []
        stress = self.trader.custom.get("stress_mode", False)
        effective_sl = 0.04 if stress else STOP_LOSS_PCT

        for pos in self.trader.open_positions:
            sym = pos.get("metadata", {}).get("symbol")
            direction = pos.get("metadata", {}).get("direction", "long")
            if not sym or sym not in prices:
                continue
            current = prices[sym]["price"]
            entry = pos["entry_price"]
            pos["current_price"] = current

            if direction == "short":
                pnl_pct = (entry - current) / entry
                pos["unrealized_pnl"] = round(pnl_pct * pos["size_usd"], 4)
                if pnl_pct < -effective_sl:
                    to_close.append((pos, current, f"SHORT_SL ({pnl_pct*100:.1f}%)"))
                    continue
                pid = pos["id"]
                low = trailing_lows.get(pid, entry)
                if current < low:
                    trailing_lows[pid] = current; low = current
                # Pas de TP partiel chez Ultimate V2 — all-in/all-out
                tp_close, tp_reason = check_tp(pos, current, trailing, trailing_lows)
                if tp_close:
                    to_close.append((pos, current, tp_reason)); continue
                if low < entry:
                    rise = (current - low) / low
                    if rise > TRAILING_SL_PCT:
                        to_close.append((pos, current, f"SHORT_TRAIL_SL"))
            else:
                pos["unrealized_pnl"] = round((current / entry - 1) * pos["size_usd"], 4)
                pnl_pct = (current - entry) / entry
                if pnl_pct < -effective_sl:
                    to_close.append((pos, current, f"SL_LONG ({pnl_pct*100:.1f}%)"))
                    continue
                pid = pos["id"]
                high = trailing.get(pid, entry)
                if current > high:
                    trailing[pid] = current; high = current
                # HARD_TP a +5% (signature Ultimate V2)
                if pnl_pct >= 0.05:
                    to_close.append((pos, current, f"HARD_TP (+{pnl_pct*100:.1f}%)")); continue
                # TRAIL_TP apres profit
                tp_close, tp_reason = check_tp(pos, current, trailing, trailing_lows)
                if tp_close:
                    to_close.append((pos, current, tp_reason)); continue
                if high > entry:
                    drop = (current - high) / high
                    if drop < -TRAILING_SL_PCT:
                        to_close.append((pos, current, f"TRAIL_LONG ({drop*100:.1f}%)"))

        self.trader.custom["trailing_highs"] = trailing
        self.trader.custom["trailing_lows"] = trailing_lows

        for pos, price, reason in to_close:
            direction = pos.get("metadata", {}).get("direction", "long")
            trade = self.trader.sell(pos["id"], price, reason=reason)
            if trade:
                if direction == "short":
                    entry = pos["entry_price"]
                    real = (entry - price) / entry * pos["size_usd"]
                    trade["realized_pnl"] = round(real, 4)
                rpnl = trade.get("realized_pnl", 0)
                update_cooldown_on_close(self.trader.custom, pos.get('metadata', {}).get('symbol', ''), direction, rpnl > 0)
                _local_update_blacklist(self.trader.custom, pos.get('metadata', {}).get('symbol', ''), direction, rpnl > 0, sl_triggered=('SL' in reason))
                trailing.pop(pos["id"], None); trailing_lows.pop(pos["id"], None)

    def rebalance(self, prices):
        regime, short_ok, long_ok, fng, btc_7d, btc_24h, btc_4h, stress = get_macro_regime()
        self.trader.custom["macro_regime"] = regime
        self.trader.custom["stress_mode"] = stress
        self.trader.custom["fear_greed"] = fng
        self.trader.append_log("MACRO", f"{regime} | F&G={fng} BTC 24h={btc_24h:+.1f}% 4h={btc_4h:+.1f}% | L={long_ok} S={short_ok}")

        news = collect_news()
        self.trader.append_log("INFO", f"News: {len(news)}")
        if len(news) < 3:
            self.trader.append_log("SKIP", "Not enough news"); return

        sentiments, scored = score_all_news(news)
        self.trader.custom["coin_sentiments"] = sentiments

        # Triple signal : sent + H + slope (slope local du coin)
        candidates_long = []
        candidates_short = []
        for coin, s in sentiments.items():
            if coin in BLACKLIST:
                continue
            if coin not in prices:
                continue
            sent = s["score"]
            H = compute_health_score(coin, prices)
            slope = prices[coin].get("change_24h", 0) / 100.0  # en fraction
            # LONG : conviction haute = tous les signaux alignes
            if sent >= SENT_MIN and H >= H_MIN and slope >= SLOPE_MIN:
                conviction = sent + H + slope  # composite ranking
                candidates_long.append((coin, sent, H, slope, conviction))
            # SHORT : sent bas + slope negatif (rare, Ultimate V2 trade peu de shorts)
            elif sent <= 0.40 and slope <= -SLOPE_MIN:
                candidates_short.append((coin, sent, H, slope, sent + slope))

        candidates_long.sort(key=lambda x: -x[4])
        candidates_short.sort(key=lambda x: x[4])

        self.trader.append_log("CONVICTION",
            f"LONG candidates: {[c[0] for c in candidates_long[:4]]} | SHORT: {[c[0] for c in candidates_short[:2]]}")

        # Sizing : conviction haute = positions plus grosses (boost 1.5x sur top conviction)
        current_syms = set(p.get("metadata", {}).get("symbol") for p in self.trader.open_positions)
        available = self.trader.equity * (1 - CASH_RESERVE_PCT) * LEVERAGE
        per_pos = available / MAX_POSITIONS if MAX_POSITIONS else 0

        # LONGS
        if long_ok:
            for i, (coin, sent, H, slope, conv) in enumerate(candidates_long[:MAX_POSITIONS]):
                if len(self.trader.open_positions) >= MAX_POSITIONS: break
                if coin in current_syms: continue
                size = per_pos * (1.5 if i == 0 else 1.0)  # le top get conviction boost
                if size < 5: continue
                if should_veto_entry(coin, 'long', prices): continue
                if check_cooldown(self.trader.custom, coin, 'long'): continue
                if _local_check_blacklist(self.trader.custom, coin, 'long'): continue
                price = prices[coin]["price"]
                pos = self.trader.buy(coin, size, price,
                    reason=f"LONG sent={sent:.2f} H={H:.2f} slope={slope*100:+.1f}%",
                    metadata={"symbol": coin, "direction": "long",
                              "sentiment_score": sent, "H_score": H, "slope": slope})
                if pos:
                    self.trader.custom["trailing_highs"][pos["id"]] = price
                    self.trader.append_log("BUY", f"LONG {coin} size=${size:.0f} (conv={conv:.2f})")

        # SHORTS (rares pour Ultimate V2 : 15 sur 59, donc max 1 short ouvert)
        if short_ok and not stress and len([p for p in self.trader.open_positions if p.get("metadata",{}).get("direction") == "short"]) == 0:
            for coin, sent, H, slope, conv in candidates_short[:1]:
                if coin in current_syms: continue
                size = per_pos
                if size < 5: continue
                if should_veto_entry(coin, 'short', prices): continue
                if check_cooldown(self.trader.custom, coin, 'short'): continue
                if _local_check_blacklist(self.trader.custom, coin, 'short'): continue
                price = prices[coin]["price"]
                pos = self.trader.buy(f"SHORT-{coin}", size, price,
                    reason=f"SHORT sent={sent:.2f} slope={slope*100:+.1f}%",
                    metadata={"symbol": coin, "direction": "short",
                              "sentiment_score": sent, "slope": slope})
                if pos:
                    self.trader.custom["trailing_lows"][pos["id"]] = price
                    self.trader.append_log("BUY", f"SHORT {coin} size=${size:.0f}")

        self.trader.custom["last_rebalance_ts"] = time.time()
        self.trader.custom["rebalance_count"] += 1

    def run_cycle(self):
        self.trader.tick()
        prices = fetch_prices_cached()
        if not prices:
            self.trader.append_log("WARN", "No prices")
            self.trader.append_equity_point(); self.trader.save_state(); return
        for pos in self.trader.open_positions:
            sym = pos.get("metadata", {}).get("symbol")
            d_ = pos.get("metadata", {}).get("direction", "long")
            if sym in prices:
                cur = prices[sym]["price"]; pos["current_price"] = cur; entry = pos["entry_price"]
                pos["unrealized_pnl"] = round((entry - cur) / entry * pos["size_usd"] if d_ == "short"
                                              else (cur / entry - 1) * pos["size_usd"], 4)
        self.trader._recalc_equity()
        self.check_stops(prices)
        if time.time() - self.trader.custom.get("last_rebalance_ts", 0) > REBALANCE_HOURS * 3600:
            self.rebalance(prices)
        self.trader.append_equity_point()
        self.trader.save_state()
        try:
            _root = Path(__file__).resolve().parent.parent.parent
            if str(_root / "bot") not in sys.path:
                sys.path.insert(0, str(_root / "bot"))
            from core.dashboard_export import export_dashboard_data
            export_dashboard_data(
                bot_keys=["sentiment_ls_v3_lo", "confluence_reverse", "ultimate_v2_reverse", "sentiment_ls_v3", "sentiment_ls_v3_tp"],
                data_dir=str(_root / "data"), dashboard_dir=str(_root / "dashboard"))
        except Exception as e:
            print(f"[WARN] dash export: {e}")


def main():
    cfg = BOT_CONFIGS["ultimate_v2_reverse"]
    bot = UltimateV2ReverseBot(cfg)
    print("=" * 60)
    print(f"  ULTIMATE V2 REVERSE-ENGINEERED")
    print(f"  Capital: ${cfg['capital']:.0f}  Lev: x{LEVERAGE}  Cycle: {cfg['cycle_seconds']}s")
    print(f"  Rebalance: {REBALANCE_HOURS}h  MIN_HOLD: {MIN_HOLD_HOURS}h  Max pos: {MAX_POSITIONS}")
    print(f"  Triple filter: sent>={SENT_MIN} H>={H_MIN} slope>=+{SLOPE_MIN*100:.0f}%")
    print(f"  Blacklist: {BLACKLIST}  (SUI a fait perdre -$2,661 a Ultimate V2 chez Zaid)")
    print("=" * 60)
    bot.trader.append_log("INFO", "Ultimate V2 reverse-engineered started")
    import random
    time.sleep(random.randint(20, 90))
    while True:
        try:
            bot.run_cycle()
        except KeyboardInterrupt:
            bot.trader.append_log("INFO", "stopped"); bot.trader.write_heartbeat("stopped"); bot.trader.save_state(); break
        except Exception as e:
            bot.trader.append_log("ERROR", f"{e}\n{traceback.format_exc()}")
            print(f"[ERR] {e}"); time.sleep(60)
        time.sleep(cfg["cycle_seconds"])


if __name__ == "__main__":
    main()
