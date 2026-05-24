"""
CONFLUENCE REVERSE-ENGINEERED
=============================
Reproduction approximative de la stratégie 'Confluence' de Zaid
(PF 1.21, +12.9% sur 23 jours, 100 trades). Analysée 2026-05-23
depuis les closed_trades exposés sur api.vercel.

Caractéristiques observées chez Zaid:
- Score COMPOSITE 'confluence' = sentiment + momentum + volume (multi-signal)
- LONG-SHORT (78L/22S, WR 71%/64%, SHORTS rentables ici)
- Holding median 11.6h (P25=4h, P75=27h)  -> plus dynamique que LS V3
- Position size ~$8,700 median (gros sizing)
- TP1_PARTIAL 33% @ +3%, TP2_PARTIAL 33% @ +5%, TRAIL_TP sur reste
- Stop-loss SERRÉ ~3-4% (worst trade observé: -3.39%)
- CONFLUENCE_FLIP: sortie défensive quand score s'inverse
- 4.3 trades/jour
- 39k articles processed = TOUTES les sources scoreées
"""

import sys, os, time, traceback
from datetime import datetime, timezone
from pathlib import Path

# Re-utilise la machinerie commune (news, scoring, prix, macro)
_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

# Auto-load .env from CRYPTO_BOT_LIVE root
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
    PRIORITY_COINS,
)

# ============================================================
# CONFLUENCE PARAMS (deduits de l'analyse 100 trades)
# ============================================================
REBALANCE_HOURS  = 2          # plus dynamique que LS V3 (vs 4h)
MIN_HOLD_HOURS   = 4          # holding court (vs 24h LS V3)
MAX_POSITIONS    = 12         # plus actif
CASH_RESERVE_PCT = 0.10
STOP_LOSS_PCT    = 0.04       # SERRE: worst trade Confluence observé = -3.4%
TRAILING_SL_PCT  = 0.08
LONG_PCT         = 0.30       # top 30% des coins (vs 20% LS V3, plus actif)
LEVERAGE         = 10

# Composite "confluence" thresholds
LONG_CONFLUENCE_MIN  = 0.55   # composite score requis pour LONG
SHORT_CONFLUENCE_MAX = 0.45   # composite score max pour SHORT
LONG_SENT_MIN        = 0.55
SHORT_SENT_MAX       = 0.45

# Blacklist coins (data Zaid)
BLACKLIST = {"DOGE", "FET"}

def compute_confluence_score(coin, sentiment_score, prices):
    """Score composite: 50% sentiment + 30% momentum 24h + 20% volume.
    Renvoie un float [0,1] ou None si data insuffisante."""
    if coin not in prices or prices[coin].get("price", 0) <= 0:
        return None
    px = prices[coin]
    chg = px.get("change_24h", 0)
    vol = px.get("volume_24h", 0)

    # Sentiment dans [0,1]
    s = max(0.0, min(1.0, sentiment_score))

    # Momentum 24h -> [0,1] (centré sur 0%, saturé à ±10%)
    m = max(0.0, min(1.0, 0.5 + chg / 20.0))

    # Volume relatif -> log-normalisé (~0.5 = volume moyen)
    import math
    v = max(0.0, min(1.0, math.log10(max(vol, 1)) / 10.0))

    return 0.50 * s + 0.30 * m + 0.20 * v


class ConfluenceReverseBot:
    """Reproduction approximative de Confluence."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.trader = PaperTrader(
            bot_id="confluence_reverse",
            initial_capital=cfg["capital"],
            state_file="confluence_reverse_state.json",
            log_file="confluence_reverse_log.json",
            equity_file="confluence_reverse_equity.json",
            heartbeat_file="heartbeat_confluence_reverse.json",
            fee_bps=2, slippage_bps=2, leverage=LEVERAGE,
        )
        defaults = {
            "last_rebalance_ts": 0, "rebalance_count": 0,
            "trailing_highs": {}, "trailing_lows": {},
            "coin_confluence": {},
        }
        for k, v in defaults.items():
            self.trader.custom.setdefault(k, v)

    def check_stops(self, prices):
        trailing = self.trader.custom.get("trailing_highs", {})
        trailing_lows = self.trader.custom.get("trailing_lows", {})
        to_close = []
        stress = self.trader.custom.get("stress_mode", False)
        effective_sl = 0.02 if stress else STOP_LOSS_PCT  # encore plus serré en stress

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
                    to_close.append((pos, current, f"SHORT_STOP_LOSS ({pnl_pct*100:.1f}%)"))
                    continue
                pid = pos["id"]
                low = trailing_lows.get(pid, entry)
                if current < low:
                    trailing_lows[pid] = current; low = current
                # TP partial pour SHORTS
                meta = pos.setdefault("metadata", {})
                if pnl_pct >= 0.03 and not meta.get("tp1_done"):
                    self.trader.partial_close(pos["id"], 0.33, current, f"SHORT_TP1_PARTIAL_33% (+{pnl_pct*100:.1f}%)")
                    meta["tp1_done"] = True
                    continue
                if pnl_pct >= 0.05 and not meta.get("tp2_done"):
                    self.trader.partial_close(pos["id"], 0.50, current, f"SHORT_TP2_PARTIAL_50%rem (+{pnl_pct*100:.1f}%)")
                    meta["tp2_done"] = True
                    continue
                if not meta.get("tp2_done"):
                    tp_close, tp_reason = check_tp(pos, current, trailing, trailing_lows)
                    if tp_close:
                        to_close.append((pos, current, tp_reason)); continue
                if low < entry:
                    rise = (current - low) / low
                    if rise > TRAILING_SL_PCT:
                        to_close.append((pos, current, f"SHORT_TRAIL_SL (+{rise*100:.1f}%)"))
            else:
                # LONG
                pos["unrealized_pnl"] = round((current / entry - 1) * pos["size_usd"], 4)
                pnl_pct = (current - entry) / entry
                if pnl_pct < -effective_sl:
                    to_close.append((pos, current, f"STOP_LOSS ({pnl_pct*100:.1f}%)"))
                    continue
                pid = pos["id"]
                high = trailing.get(pid, entry)
                if current > high:
                    trailing[pid] = current; high = current
                # TP partial (style Confluence)
                meta = pos.setdefault("metadata", {})
                if pnl_pct >= 0.03 and not meta.get("tp1_done"):
                    self.trader.partial_close(pos["id"], 0.33, current, f"TP1_PARTIAL_33% (+{pnl_pct*100:.1f}%)")
                    meta["tp1_done"] = True
                    continue
                if pnl_pct >= 0.05 and not meta.get("tp2_done"):
                    self.trader.partial_close(pos["id"], 0.50, current, f"TP2_PARTIAL_50%rem (+{pnl_pct*100:.1f}%)")
                    meta["tp2_done"] = True
                    continue
                if not meta.get("tp2_done"):
                    tp_close, tp_reason = check_tp(pos, current, trailing, trailing_lows)
                    if tp_close:
                        to_close.append((pos, current, tp_reason)); continue
                if high > entry:
                    drop = (current - high) / high
                    if drop < -TRAILING_SL_PCT:
                        to_close.append((pos, current, f"TRAIL_SL ({drop*100:.1f}%)"))

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
                _local_update_blacklist(self.trader.custom, pos.get('metadata', {}).get('symbol', ''), direction, rpnl > 0, sl_triggered=('STOP_LOSS' in reason))
                trailing.pop(pos["id"], None); trailing_lows.pop(pos["id"], None)

    def rebalance(self, prices):
        regime, short_ok, long_ok, fng, btc_7d, btc_24h, btc_4h, stress = get_macro_regime()
        self.trader.custom["macro_regime"] = regime
        self.trader.custom["stress_mode"] = stress
        self.trader.custom["fear_greed"] = fng
        self.trader.append_log("MACRO", f"{regime} | F&G={fng} BTC 24h={btc_24h:+.1f}% 4h={btc_4h:+.1f}% | L={long_ok} S={short_ok}")

        # 1. Collect news
        news = collect_news()
        self.trader.append_log("INFO", f"News collected: {len(news)} articles")
        if len(news) < 3:
            self.trader.append_log("SKIP", "Not enough news"); return

        # 2. Score sentiment
        sentiments, scored = score_all_news(news)
        self.trader.custom["coin_sentiments"] = sentiments

        # 3. Compute COMPOSITE confluence scores
        confluence_scores = {}
        for coin, s in sentiments.items():
            if coin in BLACKLIST:
                continue
            c = compute_confluence_score(coin, s["score"], prices)
            if c is not None:
                confluence_scores[coin] = {"confluence": c, "sentiment": s["score"], "count": s["count"]}
        self.trader.custom["coin_confluence"] = confluence_scores

        ranked = sorted(confluence_scores.items(), key=lambda x: -x[1]["confluence"])
        n_pick = max(1, int(len(ranked) * LONG_PCT))
        top = [c for c, d in ranked[:n_pick] if d["confluence"] >= LONG_CONFLUENCE_MIN and d["sentiment"] >= LONG_SENT_MIN]
        bot_ = [c for c, d in ranked[-n_pick:] if d["confluence"] <= SHORT_CONFLUENCE_MAX and d["sentiment"] <= SHORT_SENT_MAX]
        self.trader.append_log("CONFLUENCE", f"LONG={top[:5]} | SHORT={bot_[:5]}")

        # 4. CONFLUENCE_FLIP: sortir si score s'inverse
        for pos in list(self.trader.open_positions):
            sym = pos.get("metadata", {}).get("symbol")
            d_ = pos.get("metadata", {}).get("direction", "long")
            opened = pos.get("opened_at", "")
            if opened:
                try:
                    op_t = datetime.fromisoformat(opened.replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - op_t).total_seconds() / 3600 < MIN_HOLD_HOURS:
                        continue
                except: pass
            curr_c = confluence_scores.get(sym, {}).get("confluence", 0.5)
            if d_ == "long" and curr_c < 0.40:
                price = prices.get(sym, {}).get("price", pos["entry_price"])
                t = self.trader.sell(pos["id"], price, reason=f"CONFLUENCE_FLIP (c={curr_c:.2f})")
                if t:
                    update_cooldown_on_close(self.trader.custom, sym, "long", t.get("realized_pnl", 0) > 0)
            elif d_ == "short" and curr_c > 0.60:
                price = prices.get(sym, {}).get("price", pos["entry_price"])
                entry = pos["entry_price"]
                t = self.trader.sell(pos["id"], price, reason=f"CONFLUENCE_FLIP_SHORT (c={curr_c:.2f})")
                if t:
                    real = (entry - price) / entry * pos["size_usd"]
                    t["realized_pnl"] = round(real, 4)

        # 5. Open positions
        current_syms = set(p.get("metadata", {}).get("symbol") for p in self.trader.open_positions)
        available = self.trader.equity * (1 - CASH_RESERVE_PCT) * LEVERAGE
        per_pos = available / MAX_POSITIONS if MAX_POSITIONS else 0

        # LONGS
        if long_ok:
            for coin in top:
                if len(self.trader.open_positions) >= MAX_POSITIONS: break
                if coin in current_syms: continue
                if coin not in prices or prices[coin]["price"] <= 0: continue
                size = per_pos * (1.3 if coin in PRIORITY_COINS else 1.0)
                if size < 5: continue
                if should_veto_entry(coin, 'long', prices): continue
                if check_cooldown(self.trader.custom, coin, 'long'): continue
                if _local_check_blacklist(self.trader.custom, coin, 'long'): continue
                price = prices[coin]["price"]
                pos = self.trader.buy(coin, size, price,
                    reason=f"LONG c={confluence_scores[coin]['confluence']:.2f} s={confluence_scores[coin]['sentiment']:.2f}",
                    metadata={"symbol": coin, "direction": "long",
                              "confluence_score": confluence_scores[coin]["confluence"],
                              "sentiment_score": confluence_scores[coin]["sentiment"]})
                if pos:
                    self.trader.custom["trailing_highs"][pos["id"]] = price
                    self.trader.append_log("BUY", f"LONG {coin} @ ${price:.4f} size=${size:.0f} c={confluence_scores[coin]['confluence']:.2f}")

        # SHORTS (Confluence shorts sont rentables : 22 trades, WR 64%, +$734)
        if short_ok and not stress:
            for coin in bot_:
                if len(self.trader.open_positions) >= MAX_POSITIONS: break
                if coin in current_syms: continue
                if coin not in prices or prices[coin]["price"] <= 0: continue
                size = per_pos
                if size < 5: continue
                if should_veto_entry(coin, 'short', prices): continue
                if check_cooldown(self.trader.custom, coin, 'short'): continue
                if _local_check_blacklist(self.trader.custom, coin, 'short'): continue
                price = prices[coin]["price"]
                pos = self.trader.buy(f"SHORT-{coin}", size, price,
                    reason=f"SHORT c={confluence_scores[coin]['confluence']:.2f} s={confluence_scores[coin]['sentiment']:.2f}",
                    metadata={"symbol": coin, "direction": "short",
                              "confluence_score": confluence_scores[coin]["confluence"],
                              "sentiment_score": confluence_scores[coin]["sentiment"]})
                if pos:
                    self.trader.custom["trailing_lows"][pos["id"]] = price
                    self.trader.append_log("BUY", f"SHORT {coin} @ ${price:.4f} size=${size:.0f} c={confluence_scores[coin]['confluence']:.2f}")

        self.trader.custom["last_rebalance_ts"] = time.time()
        self.trader.custom["rebalance_count"] += 1

    def run_cycle(self):
        self.trader.tick()
        prices = fetch_prices_cached()
        if not prices:
            self.trader.append_log("WARN", "No prices")
            self.trader.append_equity_point(); self.trader.save_state(); return
        # MTM
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
        # dashboard export
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
    cfg = BOT_CONFIGS.get("confluence_reverse", {
        "name": "Confluence Reverse", "capital": 10000.0, "cycle_seconds": 300,
        "state_file": "confluence_reverse_state.json", "log_file": "confluence_reverse_log.json",
        "equity_file": "confluence_reverse_equity.json", "heartbeat_file": "heartbeat_confluence_reverse.json",
    })
    bot = ConfluenceReverseBot(cfg)
    print("=" * 60)
    print(f"  CONFLUENCE REVERSE-ENGINEERED")
    print(f"  Capital: ${cfg['capital']:.0f}  Lev: x{LEVERAGE}  Cycle: {cfg['cycle_seconds']}s")
    print(f"  Rebalance: {REBALANCE_HOURS}h  MIN_HOLD: {MIN_HOLD_HOURS}h  Max pos: {MAX_POSITIONS}")
    print(f"  SL: {STOP_LOSS_PCT*100:.0f}% (serre)  Trailing: {TRAILING_SL_PCT*100:.0f}%")
    print(f"  Blacklist: {BLACKLIST}")
    print("=" * 60)
    bot.trader.append_log("INFO", "Confluence reverse-engineered started")
    import random
    time.sleep(random.randint(20, 90))  # stagger anti rate-limit
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
