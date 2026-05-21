"""Market intelligence — couches additionnelles pour upgrader le bot.

Inspiré des meilleures techniques pro 2026 :
1. Fear & Greed Index (contrarian)
2. Funding rate Hyperliquid (sentiment dérivés)
3. Volume confirmation (institutionnel vs retail)
4. BTC dominance (macro filter)
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)


# ===== 1. FEAR & GREED INDEX =====

_FG_CACHE = {"ts": 0, "data": None}

def get_fear_greed() -> Optional[dict]:
    """Récupère le Crypto Fear & Greed Index. Cache 1h."""
    now = time.time()
    if _FG_CACHE["data"] and now - _FG_CACHE["ts"] < 3600:
        return _FG_CACHE["data"]
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=10)
        d = r.json()
        if d.get("data"):
            v = d["data"][0]
            result = {
                "value": int(v["value"]),                # 0-100
                "label": v["value_classification"],     # Extreme Fear/Fear/Neutral/Greed/Extreme Greed
                "ts": int(v["timestamp"]),
            }
            _FG_CACHE.update({"ts": now, "data": result})
            return result
    except Exception as e:
        log.warning("F&G err: %s", e)
    return None


def fear_greed_bias() -> float:
    """Retourne un biais [-0.15, +0.15] à ajouter au score sentiment.

    Contrarian:
    - Extreme Fear (0-25)  → +0.15 (bullish bias)
    - Fear (26-45)         → +0.05
    - Neutral (46-55)      → 0
    - Greed (56-75)        → -0.05
    - Extreme Greed (76-100) → -0.15 (bearish bias)
    """
    fg = get_fear_greed()
    if not fg:
        return 0.0
    v = fg["value"]
    if v <= 25: return 0.15
    if v <= 45: return 0.05
    if v <= 55: return 0.0
    if v <= 75: return -0.05
    return -0.15


# ===== 2. FUNDING RATE HYPERLIQUID =====

_FUNDING_CACHE = {"ts": 0, "data": {}}

def get_hyperliquid_funding() -> dict[str, float]:
    """Récupère les funding rates de toutes les paires Hyperliquid. Cache 5 min."""
    now = time.time()
    if _FUNDING_CACHE["data"] and now - _FUNDING_CACHE["ts"] < 300:
        return _FUNDING_CACHE["data"]
    try:
        r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "metaAndAssetCtxs"}, timeout=10)
        data = r.json()
        if not data or len(data) < 2:
            return {}
        universe = data[0].get("universe", [])
        ctxs = data[1]
        result = {}
        for i, asset in enumerate(universe):
            if i < len(ctxs):
                funding = float(ctxs[i].get("funding", 0))  # taux annualisé déjà ?
                result[asset["name"]] = funding
        _FUNDING_CACHE.update({"ts": now, "data": result})
        return result
    except Exception as e:
        log.warning("funding err: %s", e)
        return {}


def funding_bias(coin: str) -> float:
    """Retourne un biais [-0.10, +0.10] basé sur le funding rate.

    Funding très positif (longs surchargés) → bias bearish (push to short)
    Funding très négatif (shorts surchargés) → bias bullish (push to long)
    """
    rates = get_hyperliquid_funding()
    f = rates.get(coin)
    if f is None:
        return 0.0
    # Hyperliquid funding est en taux horaire (typique 0.00001 = 0.001% par heure)
    # 0.01% par heure = 87.6% annualisé = extreme greed
    annual = f * 24 * 365
    if annual > 0.5:  return -0.10  # 50%+ annualisé = extreme bullish positioning → SHORT
    if annual > 0.2:  return -0.05
    if annual > -0.2: return 0.0
    if annual > -0.5: return 0.05
    return 0.10  # funding très négatif = shorts saturés → LONG


# ===== 3. VOLUME CONFIRMATION =====

_VOL_CACHE = {"ts": 0, "data": {}}

def get_24h_volumes() -> dict[str, dict]:
    """Récupère volume 24h + prix de toutes les paires Hyperliquid. Cache 5 min."""
    now = time.time()
    if _VOL_CACHE["data"] and now - _VOL_CACHE["ts"] < 300:
        return _VOL_CACHE["data"]
    try:
        r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "metaAndAssetCtxs"}, timeout=10)
        data = r.json()
        if not data or len(data) < 2:
            return {}
        universe = data[0].get("universe", [])
        ctxs = data[1]
        result = {}
        for i, asset in enumerate(universe):
            if i < len(ctxs):
                c = ctxs[i]
                result[asset["name"]] = {
                    "mark": float(c.get("markPx", 0)),
                    "vol_24h": float(c.get("dayNtlVlm", 0)),
                    "open_int": float(c.get("openInterest", 0)),
                    "prev_day_px": float(c.get("prevDayPx", 0)),
                }
        _VOL_CACHE.update({"ts": now, "data": result})
        return result
    except Exception as e:
        log.warning("vol err: %s", e)
        return {}


def volume_ok(coin: str, min_volume_usd: float = 50_000_000) -> bool:
    """Volume 24h suffisant pour éviter les arnaques / slippage."""
    v = get_24h_volumes().get(coin, {})
    return v.get("vol_24h", 0) >= min_volume_usd


def price_change_24h_pct(coin: str) -> Optional[float]:
    """Change 24h en %."""
    v = get_24h_volumes().get(coin, {})
    mark = v.get("mark", 0)
    prev = v.get("prev_day_px", 0)
    if mark == 0 or prev == 0:
        return None
    return (mark - prev) / prev * 100


# ===== 4. BTC DOMINANCE / MARKET REGIME =====

_BTCD_CACHE = {"ts": 0, "value": None}

def get_btc_dominance() -> Optional[float]:
    """BTC dominance via CoinGecko. Cache 30 min."""
    now = time.time()
    if _BTCD_CACHE["value"] and now - _BTCD_CACHE["ts"] < 1800:
        return _BTCD_CACHE["value"]
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        d = r.json()
        btcd = float(d["data"]["market_cap_percentage"]["btc"])
        _BTCD_CACHE.update({"ts": now, "value": btcd})
        return btcd
    except Exception as e:
        log.warning("btc.d err: %s", e)
        return None


# ===== AGRÉGATEUR : enrichit un score sentiment avec tous les biais =====

def enriched_score(coin: str, base_sentiment: float) -> tuple[float, dict]:
    """Combine sentiment news + Fear&Greed + funding rate.

    Retourne (score_enrichi, breakdown_dict)
    """
    fg = fear_greed_bias()
    fr = funding_bias(coin) if coin in get_24h_volumes() else 0.0
    enriched = base_sentiment + fg + fr
    enriched = max(0.0, min(1.0, enriched))
    return enriched, {
        "base_sentiment": round(base_sentiment, 3),
        "fear_greed_bias": round(fg, 3),
        "funding_bias": round(fr, 3),
        "final_score": round(enriched, 3),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== Fear & Greed ===")
    print(get_fear_greed())
    print(f"Bias: {fear_greed_bias():+.2f}")
    print()
    print("=== Funding rates (sample) ===")
    fr = get_hyperliquid_funding()
    for c in ["BTC", "ETH", "SOL", "SUI", "LINK"]:
        if c in fr:
            print(f"  {c}: {fr[c]:+.6f} (annualized: {fr[c]*24*365*100:+.1f}%)")
    print()
    print("=== Volumes 24h ===")
    vols = get_24h_volumes()
    for c in ["BTC", "ETH", "SOL"]:
        v = vols.get(c, {})
        print(f"  {c}: vol=${v.get('vol_24h',0)/1e6:.0f}M  mark=${v.get('mark',0)}  Δ24h={price_change_24h_pct(c)}")
    print()
    print("=== BTC Dominance ===")
    print(f"  {get_btc_dominance()}%")
    print()
    print("=== Enriched score BTC base=0.50 ===")
    score, breakdown = enriched_score("BTC", 0.50)
    print(breakdown)
