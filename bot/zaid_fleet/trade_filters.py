"""
Trade Filters Module — 3 symmetric filters for all bots.
1. Veto technique: block entries against strong momentum
2. Cooldown: 3 consecutive losses on same coin+direction = skip 48h
3. TP: 5% hard cap + trailing activated at 3%

Import in any bot:
    from trade_filters import should_veto_entry, check_cooldown, update_cooldown_on_close, check_tp

All filters are SYMMETRIC (same rules for longs and shorts).
"""
import time

# ──────────────────────────────────────────────
# FILTER 1: Veto technique
# ──────────────────────────────────────────────

def should_veto_entry(coin, direction, prices):
    """Block entry if coin has strong momentum AGAINST the trade direction.
    - SHORT blocked if coin is up >3% in 24h (strong uptrend, not reversing yet)
    - LONG blocked if coin is down >3% in 24h (strong downtrend, catching knife)
    Returns True if trade should be BLOCKED.
    """
    if coin not in prices:
        return False
    change_24h = prices[coin].get("change_24h", 0)
    if direction == "short" and change_24h > 3.0:
        return True
    if direction == "long" and change_24h < -3.0:
        return True
    return False


# ──────────────────────────────────────────────
# FILTER 2: Cooldown dynamique
# ──────────────────────────────────────────────

MAX_STREAK = 3
COOLDOWN_HOURS = 48

def check_cooldown(custom, coin, direction):
    """Check if a coin+direction is in cooldown after 3 consecutive losses.
    Returns True if trade should be BLOCKED.
    """
    key = f"cooldown_{direction}_{coin}"
    cooldown_until = custom.get(key, 0)
    return time.time() < cooldown_until


def update_cooldown_on_close(custom, coin, direction, won):
    """Call after every trade close to update streak and cooldown state."""
    streak_key = f"streak_{direction}_{coin}"
    cooldown_key = f"cooldown_{direction}_{coin}"
    if won:
        custom[streak_key] = 0
    else:
        custom[streak_key] = custom.get(streak_key, 0) + 1
        if custom[streak_key] >= MAX_STREAK:
            custom[cooldown_key] = time.time() + COOLDOWN_HOURS * 3600


# ──────────────────────────────────────────────
# FILTER 3: Take-Profit
# ──────────────────────────────────────────────

TP_HARD_PCT = 0.05       # 5% hard cap
TP_ACTIVATE_PCT = 0.03   # trailing activates at +3%
TP_LOCK_PCT = 0.03       # lock at +3% once activated

def check_tp(pos, current_price, trailing_highs, trailing_lows):
    """Check if position should be closed by TP logic.
    Returns (should_close, reason) tuple.
    """
    entry = pos.get("entry_price", 0)
    if entry <= 0:
        return False, ""

    direction = pos.get("metadata", {}).get("direction", "long")
    pid = pos.get("id", "")

    if direction == "short":
        pnl_pct = (entry - current_price) / entry
        # Hard TP
        if pnl_pct >= TP_HARD_PCT:
            return True, f"SHORT_HARD_TP (+{pnl_pct*100:.1f}%)"
        # Trailing TP
        low = trailing_lows.get(pid, entry)
        if current_price < low:
            trailing_lows[pid] = current_price
            low = current_price
        peak_pnl = (entry - low) / entry if entry > 0 else 0
        if peak_pnl >= TP_ACTIVATE_PCT and pnl_pct < TP_LOCK_PCT:
            return True, f"SHORT_TRAIL_TP (peak=+{peak_pnl*100:.1f}% now={pnl_pct*100:.1f}%)"
    else:
        pnl_pct = (current_price - entry) / entry
        # Hard TP
        if pnl_pct >= TP_HARD_PCT:
            return True, f"HARD_TP (+{pnl_pct*100:.1f}%)"
        # Trailing TP
        high = trailing_highs.get(pid, entry)
        if current_price > high:
            trailing_highs[pid] = current_price
            high = current_price
        peak_pnl = (high - entry) / entry if entry > 0 else 0
        if peak_pnl >= TP_ACTIVATE_PCT and pnl_pct < TP_LOCK_PCT:
            return True, f"TRAIL_TP (peak=+{peak_pnl*100:.1f}% now={pnl_pct*100:.1f}%)"

    return False, ""
