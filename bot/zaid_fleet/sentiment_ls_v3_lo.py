"""
SENTIMENT LONG-ONLY V3 ULTRA — 148 SOURCES (RSS + Reddit + APIs + Research)
==============================================================================
LONG-ONLY VERSION: this bot only opens LONG positions on coins with
high sentiment. No shorts. Uses the same news/scoring stack and
macro multi-TF + circuit breaker as LS V3.
"""

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# Load .env from CRYPTO_BOT_LIVE root (no python-dotenv dependency needed)
for _candidate in (
    Path(__file__).resolve().parent / ".env",                        # bot/zaid_fleet/.env
    Path(__file__).resolve().parent.parent.parent / ".env",          # CRYPTO_BOT_LIVE/.env
):
    if _candidate.exists():
        for _line in _candidate.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
        break

from price_cache import get_cached_prices
from paper_engine import PaperTrader, safe_json_write
from trade_filters import should_veto_entry, check_cooldown, update_cooldown_on_close, check_tp
from paper_config import BOT_CONFIGS
from crypto_news_sources import RSS_FEEDS as ALL_RSS, RESEARCH_FEEDS, MEDIUM_FEEDS

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENROUTER_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

NEWS_API = "https://cryptocurrency.cv/api"
CRYPTOPANIC_API = "https://cryptopanic.com/api/v1/posts/"

REBALANCE_HOURS = 4           # Rebalance every 4h
MIN_ARTICLES = 5              # Min articles to generate signal (was 2)
LONG_PCT = 0.20               # Top 20% = long
MIN_SCORE_TO_BUY = 0.65       # Min sentiment score to enter (was 0.60)
SHORT_THRESHOLD = 0.40         # Short coins below this score
MAX_POSITIONS = 8             # Max 8 positions (longs + shorts)
CASH_RESERVE_PCT = 0.10       # 10% cash reserve
MIN_HOLD_HOURS = 24            # Don't sell before 4h
STOP_LOSS_PCT = 0.08          # 8% stop-loss
TRAILING_SL_PCT = 0.10        # 6% trailing stop after profit
SHORT_EXIT_SCORE = 0.62       # Close short when sentiment rises above neutral

# Universe — 17 cryptos. DOGE (-$817, 47% WR) et FET (-$573, 0% WR) bannis
# d'après la data live du fleet Zaid (2026-05-23). RNDR aussi marginal — gardé pour now.
UNIVERSE = [
    ("bitcoin", "BTC", "BTC/USDT"),
    ("ethereum", "ETH", "ETH/USDT"),
    ("ripple", "XRP", "XRP/USDT"),
    ("avalanche-2", "AVAX", "AVAX/USDT"),
    ("chainlink", "LINK", "LINK/USDT"),
    ("uniswap", "UNI", "UNI/USDT"),
    ("near", "NEAR", "NEAR/USDT"),
    ("aptos", "APT", "APT/USDT"),
    ("arbitrum", "ARB", "ARB/USDT"),
    ("optimism", "OP", "OP/USDT"),
    # ("dogecoin", "DOGE", "DOGE/USDT"),  # BANNI — 47% WR / -$817 cumulés chez Zaid
    # ("fetch-ai", "FET", "FET/USDT"),    # BANNI — 0% WR / -$573 cumulés chez Zaid
    ("render-token", "RNDR", "RNDR/USDT"),
    ("sui", "SUI", "SUI/USDT"),
    ("injective-protocol", "INJ", "INJ/USDT"),
    ("lido-dao", "LDO", "LDO/USDT"),
    ("aave", "AAVE", "AAVE/USDT"),
    ("filecoin", "FIL", "FIL/USDT"),
    ("ondo-finance", "ONDO", "ONDO/USDT"),
]

# Priority coins — top WR sur le fleet Zaid (ONDO 94% / LINK 88% / APT 88%)
# Position size boostée de BOOST_FACTOR sur ces 3 coins
PRIORITY_COINS = {"ONDO", "LINK", "APT"}
BOOST_FACTOR = 1.30

SYMBOL_MAP = {u[1]: u for u in UNIVERSE}  # symbol -> (cg_id, symbol, pair)
COINGECKO_API = "https://api.coingecko.com/api/v3"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────
# NEWS COLLECTION
# ─────────────────────────────────────────────

# Build master feed list from crypto_news_sources.py (148 sources)
RSS_FEEDS = []
for name, data in {**ALL_RSS, **RESEARCH_FEEDS, **MEDIUM_FEEDS}.items():
    RSS_FEEDS.append((name, data["url"], data.get("weight", 1)))

# Reddit subreddits (JSON API works, RSS doesn't)
REDDIT_SUBS = [
    "cryptocurrency", "bitcoin", "ethereum", "solana", "cardano",
    "defi", "CryptoMarkets", "altcoin", "ethtrader", "SatoshiStreetBets",
    "CryptoCurrency", "bitcoinmarkets", "ethfinance", "cosmosnetwork",
    "Chainlink", "algorand", "avalanche", "polkadot", "CryptoTechnology",
    "NFT", "web3", "binance", "0xPolygon", "arbitrum", "optimismFdn",
]


def fetch_rss_news():
    """Fetch news from ALL RSS feeds (60+ news + research + medium)."""
    import re as _re
    articles = []
    for name, url, weight in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SentimentBot/3.0)"
            }, allow_redirects=True)
            if r.status_code != 200:
                continue
            text = r.text
            items = _re.findall(r'<item>(.*?)</item>', text, _re.DOTALL)
            for item in items[:10]:  # Max 10 per feed (148 feeds * 10 = 1480 max)
                title_m = _re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', item)
                desc_m = _re.search(r'<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', item, _re.DOTALL)
                title = title_m.group(1).strip() if title_m else ""
                desc = desc_m.group(1).strip() if desc_m else ""
                desc = _re.sub(r'<[^>]+>', '', desc)[:500]
                if title:
                    articles.append({
                        "title": title[:300],
                        "body": desc,
                        "source": name,
                        "weight": weight,
                    })
        except:
            pass
        time.sleep(0.2)  # Faster — 148 feeds * 0.2s = ~30s total
    return articles


def fetch_reddit_posts():
    """Fetch top posts from crypto subreddits via JSON API."""
    articles = []
    for sub in REDDIT_SUBS:
        try:
            r = requests.get(
                f"https://www.reddit.com/r/{sub}/hot/.json?limit=10",
                timeout=10,
                headers={"User-Agent": "SentimentBot/3.0 (research)"},
            )
            if r.status_code != 200:
                continue
            posts = r.json().get("data", {}).get("children", [])
            for p in posts:
                d = p.get("data", {})
                title = d.get("title", "")
                score = d.get("score", 0)
                if title and score > 10:  # Only posts with upvotes
                    articles.append({
                        "title": title[:300],
                        "body": (d.get("selftext", "") or "")[:500],
                        "source": f"r/{sub}",
                        "weight": 1,
                        "upvotes": score,
                    })
        except:
            pass
        time.sleep(0.5)  # Reddit rate limit
    return articles


def collect_news():
    """Collect from ALL 148+ sources: RSS + Reddit + APIs."""
    all_news = []

    # 1. RSS feeds (60+ news + research + medium)
    rss_articles = fetch_rss_news()
    for a in rss_articles:
        coins = extract_coins_from_text(a["title"] + " " + a.get("body", ""))
        if coins:
            a["coins"] = coins
            a["ts"] = datetime.now(timezone.utc).isoformat()
            all_news.append(a)

    # 2. Reddit (25 subreddits)
    reddit_posts = fetch_reddit_posts()
    for a in reddit_posts:
        coins = extract_coins_from_text(a["title"] + " " + a.get("body", ""))
        if coins:
            a["coins"] = coins
            a["ts"] = datetime.now(timezone.utc).isoformat()
            all_news.append(a)

    # Deduplicate
    seen = set()
    unique = []
    for n in all_news:
        key = n["title"][:80].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(n)

    return unique


def extract_coins_from_text(text):
    """Extract mentioned coins from text."""
    text_upper = text.upper()
    found = []
    for cg_id, symbol, pair in UNIVERSE:
        # Match symbol or full name
        if symbol in text_upper or cg_id.replace("-", " ").upper() in text_upper:
            found.append(symbol)
    # Also match common names
    name_map = {
        "BITCOIN": "BTC", "ETHER": "ETH", "ETHEREUM": "ETH", "SOLANA": "SOL",
        "RIPPLE": "XRP", "CARDANO": "ADA", "AVALANCHE": "AVAX", "POLKADOT": "DOT",
        "CHAINLINK": "LINK", "DOGECOIN": "DOGE", "UNISWAP": "UNI", "FILECOIN": "FIL",
    }
    for name, sym in name_map.items():
        if name in text_upper and sym not in found:
            found.append(sym)
    return found


# ─────────────────────────────────────────────
# DEEPSEEK SENTIMENT SCORING
# ─────────────────────────────────────────────

SENTIMENT_PROMPT = """You are a crypto market sentiment analyst. Score this news for its impact on {coin} price.

HEADLINE: {title}
{body_section}

Score from 0.0 (very bearish) to 1.0 (very bullish):
- 0.0-0.2: Very negative (hack, ban, crash, fraud, lawsuit)
- 0.2-0.4: Negative (delay, sell-off, concern, downgrade)
- 0.4-0.6: Neutral (update, no clear impact)
- 0.6-0.8: Positive (partnership, adoption, upgrade, growth)
- 0.8-1.0: Very positive (ETF approval, major adoption, ATH)

Respond ONLY with: {{"score": 0.XX}}"""


def score_article_deepseek(article, coin):
    """Score a single article for a specific coin using DeepSeek."""
    body_section = f"DETAILS: {article['body'][:300]}" if article.get("body") else ""

    prompt = SENTIMENT_PROMPT.format(
        coin=coin,
        title=article["title"],
        body_section=body_section,
    )

    try:
        r = requests.post(DEEPSEEK_API, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
        }, json={
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 30,
            "temperature": 0.1,
        }, timeout=30)
        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"].strip()

        # Extract score from response
        match = re.search(r'"score"\s*:\s*(0\.\d+)', content)
        if match:
            return float(match.group(1))

        # Fallback: look for any 0.XX pattern
        match = re.search(r'0\.\d+', content)
        if match:
            return float(match.group())

    except Exception as e:
        print(f"[WARN] DeepSeek error: {e}")

    return None


def score_all_news(news_articles):
    """Score all articles and aggregate per coin."""
    coin_scores = {}  # {symbol: [scores]}
    scored_articles = []

    for article in news_articles:
        # Only score Tier 1 sources (weight=3) via DeepSeek — Tier 2-3 are noise
        if article.get("weight", 1) < 3:
            continue

        for coin in article["coins"]:
            # Add community votes as a weak signal
            community_score = None
            bull = article.get("community_bullish", 0)
            bear = article.get("community_bearish", 0)
            if bull + bear > 2:
                community_score = bull / (bull + bear)

            # DeepSeek scoring
            llm_score = score_article_deepseek(article, coin)

            if llm_score is not None:
                # Blend LLM + community if available
                if community_score is not None:
                    final_score = llm_score * 0.8 + community_score * 0.2
                else:
                    final_score = llm_score

                if coin not in coin_scores:
                    coin_scores[coin] = []
                # Weight by source tier (Tier 1 = 3x, Tier 3 = 1x)
                weight = article.get("weight", 1)
                for _ in range(weight):
                    coin_scores[coin].append(final_score)

                scored_articles.append({
                    "coin": coin,
                    "title": article["title"][:100],
                    "llm_score": round(llm_score, 3),
                    "community_score": round(community_score, 3) if community_score else None,
                    "final_score": round(final_score, 3),
                    "source": article["source"],
                })

            time.sleep(0.3)  # Rate limit DeepSeek
            # Keep heartbeat alive during long scoring
            if hasattr(score_all_news, '_trader') and score_all_news._trader:
                score_all_news._trader.write_heartbeat()

    # Aggregate: recency-weighted average (newer articles count more)
    aggregated = {}
    for coin, scores in coin_scores.items():
        if len(scores) >= MIN_ARTICLES:
            # Simple average (could add recency weighting later)
            avg = sum(scores) / len(scores)
            aggregated[coin] = {
                "score": round(avg, 4),
                "count": len(scores),
                "scores": scores,
            }

    return aggregated, scored_articles


# ─────────────────────────────────────────────
# PRICE FETCHING
# ─────────────────────────────────────────────


def fetch_prices_cached():
    """Fetch prices using shared cache, mapped to symbols."""
    raw = get_cached_prices()
    prices = {}
    for cg_id, symbol, pair in UNIVERSE:
        if cg_id in raw:
            prices[symbol] = raw[cg_id]
    return prices

def fetch_prices():
    """Fetch prices for all coins in universe. Aggressive retry."""
    ids = ",".join(u[0] for u in UNIVERSE)
    for attempt in range(3):
      try:
        r = requests.get(f"{COINGECKO_API}/simple/price", params={
            "ids": ids,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        }, timeout=15)
        r.raise_for_status()
        data = r.json()

        prices = {}
        for cg_id, symbol, pair in UNIVERSE:
            if cg_id in data:
                prices[symbol] = {
                    "price": data[cg_id].get("usd", 0),
                    "change_24h": data[cg_id].get("usd_24h_change", 0),
                }
        return prices
      except:
        time.sleep(10 * (attempt + 1))
    return {}


# ─────────────────────────────────────────────
# BOT CLASS
# ─────────────────────────────────────────────


def _btc_market_chart(days):
    """Fetch BTC price chart for given days. Returns list of prices or []."""
    try:
        r = requests.get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": days}, timeout=15)
        if r.status_code == 200:
            return [p[1] for p in r.json().get("prices", [])]
    except: pass
    return []

def get_btc_slope_7d():
    """Get BTC 7-day price slope (average of first quarter vs last quarter)."""
    prices = _btc_market_chart(7)
    if len(prices) > 10:
        q = max(1, len(prices)//4)
        first = sum(prices[:q]) / q
        last = sum(prices[-q:]) / q
        return (last - first) / first * 100
    return 0

def get_btc_slope_24h():
    """Get BTC 24h price change (last vs first)."""
    prices = _btc_market_chart(1)
    if len(prices) >= 2:
        return (prices[-1] - prices[0]) / prices[0] * 100
    return 0

def get_btc_slope_4h():
    """Get BTC 4h price change (extracted from last 24h chart, 5-min granularity)."""
    prices = _btc_market_chart(1)
    if len(prices) >= 50:
        # CoinGecko free tier returns ~5-min granularity on days=1 → 4h ≈ last 48 points
        recent = prices[-48:]
        return (recent[-1] - recent[0]) / recent[0] * 100
    return 0

# CIRCUIT BREAKER 2026-05-22 — Stress mode triggers
STRESS_THRESHOLD_24H = -3.0   # If BTC < -3% in 24h → stress
STRESS_THRESHOLD_4H = -2.0    # If BTC < -2% in 4h → stress (fast crash)
STRESS_SL_LONG = 0.04         # Tighten long SL from 8% → 4% during stress

def get_macro_regime():
    """Market regime from F&G + BTC slope 7d/24h/4h.
    Returns (regime, short_ok, long_ok, fng, btc_slope_7d, btc_slope_24h, btc_slope_4h, stress_mode)."""
    fng = 50
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        if r.status_code == 200:
            fng = int(r.json().get("data", [{}])[0].get("value", 50))
    except: pass
    btc_slope_7d = get_btc_slope_7d()
    btc_slope_24h = get_btc_slope_24h()
    btc_slope_4h = get_btc_slope_4h()

    # CIRCUIT BREAKER: fast-crash detection
    stress_mode = (btc_slope_24h < STRESS_THRESHOLD_24H) or (btc_slope_4h < STRESS_THRESHOLD_4H)
    if stress_mode:
        # Block longs, allow shorts, label STRESS regardless of 7d
        return "STRESS", True, False, fng, btc_slope_7d, btc_slope_24h, btc_slope_4h, True

    # Otherwise use combined bias (F&G + 7d slope) as before
    fng_bias = (fng - 50) / 50
    slope_bias = max(-1, min(1, btc_slope_7d / 10))
    bias = fng_bias * 0.4 + slope_bias * 0.6
    if bias < -0.3:
        return "BEAR", True, False, fng, btc_slope_7d, btc_slope_24h, btc_slope_4h, False
    elif bias < -0.1:
        return "CAUTIOUS", True, True, fng, btc_slope_7d, btc_slope_24h, btc_slope_4h, False
    elif bias > 0.3:
        return "BULL", False, True, fng, btc_slope_7d, btc_slope_24h, btc_slope_4h, False
    else:
        return "NEUTRAL", True, True, fng, btc_slope_7d, btc_slope_24h, btc_slope_4h, False


# FIX 2026-05-10 — Blacklist locale: 2 SL consécutifs sur (coin, direction) → 72h cooldown
def _local_check_blacklist(custom, coin, direction):
    import time as _t
    return _t.time() < custom.get(f"local_bl_{direction}_{coin}", 0)

def _local_update_blacklist(custom, coin, direction, won, sl_triggered=False):
    import time as _t
    streak_key = f"local_streak_{direction}_{coin}"
    bl_key = f"local_bl_{direction}_{coin}"
    if won:
        custom[streak_key] = 0
    elif sl_triggered:
        custom[streak_key] = custom.get(streak_key, 0) + 1
        if custom[streak_key] >= 2:
            custom[bl_key] = _t.time() + 72 * 3600
            custom[streak_key] = 0

class SentimentBot:

    def __init__(self, cfg):
        self.cfg = cfg
        self.trader = PaperTrader(
            bot_id="sentiment_ls_v3_lo",
            initial_capital=cfg["capital"],
            state_file=cfg["state_file"],
            log_file=cfg["log_file"],
            equity_file=cfg["equity_file"],
            heartbeat_file=cfg["heartbeat_file"],
            fee_bps=2,
            slippage_bps=2,
            leverage=10,
        )
        self._ensure_custom()

    def _ensure_custom(self):
        defaults = {
            "last_rebalance_ts": 0,
            "rebalance_count": 0,
            "coin_sentiments": {},
            "scored_articles": [],
            "articles_processed": 0,
            "deepseek_calls": 0,
            "top_coins": [],
            "bottom_coins": [],
            "short_coins": [],
            "trailing_highs": {},
            "trailing_lows": {},
        }
        for k, v in defaults.items():
            if k not in self.trader.custom:
                self.trader.custom[k] = v

    def check_stops(self, prices):
        """Check stop-loss and trailing stops for both longs and shorts."""
        trailing = self.trader.custom.get("trailing_highs", {})
        trailing_lows = self.trader.custom.get("trailing_lows", {})
        to_close = []

        # CIRCUIT BREAKER: tighten long SL during stress
        stress_mode = self.trader.custom.get("stress_mode", False)
        effective_sl_long = STRESS_SL_LONG if stress_mode else STOP_LOSS_PCT

        for pos in self.trader.open_positions:
            symbol = pos.get("metadata", {}).get("symbol")
            direction = pos.get("metadata", {}).get("direction", "long")
            if not symbol or symbol not in prices:
                continue

            current = prices[symbol]["price"]
            entry = pos["entry_price"]
            pos["current_price"] = current

            if direction == "short":
                # SHORT: profit when price goes DOWN
                pnl_pct = (entry - current) / entry
                pos["unrealized_pnl"] = round(pnl_pct * pos["size_usd"], 4)

                # Stop-loss for short = price went UP too much
                if pnl_pct < -STOP_LOSS_PCT:
                    to_close.append((pos, current, f"SHORT_STOP_LOSS ({pnl_pct*100:.1f}%)"))
                    continue

                # Trailing stop for short (only after profit)
                pid = pos["id"]
                low = trailing_lows.get(pid, entry)
                if current < low:
                    trailing_lows[pid] = current
                    low = current

                # TP CHECK (short)
                tp_close_s, tp_reason_s = check_tp(pos, current, trailing, trailing_lows)
                if tp_close_s:
                    to_close.append((pos, current, tp_reason_s))
                    continue
                if low < entry:  # Only trail after profit
                    rise = (current - low) / low
                    if rise > TRAILING_SL_PCT:
                        to_close.append((pos, current, f"SHORT_TRAIL_SL (+{rise*100:.1f}% from ${low:.2f})"))
            else:
                # LONG: standard logic
                pos["unrealized_pnl"] = round((current / entry - 1) * pos["size_usd"], 4)
                pnl_pct = (current - entry) / entry

                # Fixed stop-loss (tightened during stress)
                if pnl_pct < -effective_sl_long:
                    sl_label = "STRESS_STOP_LOSS" if stress_mode else "STOP_LOSS"
                    to_close.append((pos, current, f"{sl_label} ({pnl_pct*100:.1f}%)"))
                    continue

                # Trailing stop (only after profit)
                pid = pos["id"]
                high = trailing.get(pid, entry)
                if current > high:
                    trailing[pid] = current
                    high = current

                # === TP PARTIAL (style Confluence — best perf chez Zaid) ===
                #  TP1 +3% → vend 33% de la position originale (TP1_PARTIAL)
                #  TP2 +5% → vend 50% du restant (= ~33% de l'orig.)
                #  Reste ~34% → trailing 10% pour capturer la suite
                meta = pos.setdefault("metadata", {})
                if pnl_pct >= 0.03 and not meta.get("tp1_done"):
                    self.trader.partial_close(pos["id"], 0.33, current,
                                              f"TP1_PARTIAL_33% (+{pnl_pct*100:.1f}%)")
                    meta["tp1_done"] = True
                    continue  # next position
                if pnl_pct >= 0.05 and not meta.get("tp2_done"):
                    self.trader.partial_close(pos["id"], 0.50, current,
                                              f"TP2_PARTIAL_50%rem (+{pnl_pct*100:.1f}%)")
                    meta["tp2_done"] = True
                    continue  # next position

                # TP CHECK (long) — appelé seulement si TP2 pas encore atteint
                if not meta.get("tp2_done"):
                    tp_close, tp_reason = check_tp(pos, current, trailing, trailing_lows)
                    if tp_close:
                        to_close.append((pos, current, tp_reason))
                        continue
                if high > entry:  # Only trail after profit
                    drop = (current - high) / high
                    if drop < -TRAILING_SL_PCT:
                        to_close.append((pos, current, f"TRAIL_SL ({drop*100:.1f}% from ${high:.2f})"))

        self.trader.custom["trailing_highs"] = trailing
        self.trader.custom["trailing_lows"] = trailing_lows

        for pos, price, reason in to_close:
            direction = pos.get("metadata", {}).get("direction", "long")
            trade = self.trader.sell(pos["id"], price, reason=reason)
            if trade:
                # For shorts, recalculate realized PnL correctly
                if direction == "short":
                    entry = pos["entry_price"]
                    real_pnl = (entry - price) / entry * pos["size_usd"]
                    trade["realized_pnl"] = round(real_pnl, 4)
                rpnl = trade.get("realized_pnl", 0)
                update_cooldown_on_close(self.trader.custom, pos.get('metadata', {}).get('symbol', ''), pos.get('metadata', {}).get('direction', 'long'), rpnl > 0)
                # FIX 2026-05-10: local 2-SL blacklist hook
                _sl_trig = ('STOP_LOSS' in reason)
                _local_update_blacklist(self.trader.custom, pos.get('metadata', {}).get('symbol', ''), pos.get('metadata', {}).get('direction', 'long'), rpnl > 0, sl_triggered=_sl_trig)
                label = "WIN" if rpnl > 0 else "LOSS"
                prefix = "SHORT_" if direction == "short" else ""
                self.trader.append_log(
                    label,
                    f"{prefix}STOP {pos['symbol']} @ ${price:.4f} | PnL: ${rpnl:+.2f} | {reason}"
                )
                trailing.pop(pos["id"], None)
                trailing_lows.pop(pos["id"], None)

    def rebalance(self, prices):
        """Full rebalance cycle: collect news, score, trade. LONG-SHORT version."""
        # No Fear & Greed filter — long-short profits in all market regimes

        regime, short_ok, long_ok, fng_val, btc_sl_7d, btc_sl_24h, btc_sl_4h, stress_mode = get_macro_regime()
        self.trader.custom["macro_regime"] = regime
        self.trader.custom["fear_greed"] = fng_val
        self.trader.custom["stress_mode"] = stress_mode
        self.trader.custom["btc_slope_24h"] = round(btc_sl_24h, 2)
        self.trader.custom["btc_slope_4h"] = round(btc_sl_4h, 2)
        self.trader.append_log("MACRO", f"{regime} | F&G={fng_val} | BTC 7d={btc_sl_7d:+.1f}% 24h={btc_sl_24h:+.1f}% 4h={btc_sl_4h:+.1f}% | Short={short_ok} Long={long_ok}")
        if stress_mode:
            self.trader.append_log("CIRCUIT_BREAKER", f"STRESS MODE active — longs blocked, long SL tightened to {STRESS_SL_LONG*100:.0f}%")
        self.trader.append_log("INFO", "Starting LONG-SHORT sentiment scan (V3 Ultra 148 sources)...")

        # 1. Collect news
        news = collect_news()
        self.trader.append_log("INFO", f"Collected {len(news)} articles from {len(RSS_FEEDS)} RSS + {len(REDDIT_SUBS)} Reddit")

        if len(news) < 3:
            self.trader.append_log("SKIP", "Not enough news articles")
            return

        # 2. Score with DeepSeek
        score_all_news._trader = self.trader
        sentiments, scored = score_all_news(news)
        self.trader.custom["coin_sentiments"] = sentiments
        self.trader.custom["scored_articles"] = scored[-20:]  # Keep last 20 for dashboard
        self.trader.custom["articles_processed"] += len(news)
        self.trader.custom["deepseek_calls"] += sum(len(a["coins"]) for a in news)

        self.trader.append_log("INFO", f"Scored {len(sentiments)} coins with sentiment")

        if not sentiments:
            self.trader.append_log("SKIP", "No coins with enough articles")
            return

        # 3. Rank coins by sentiment
        ranked = sorted(sentiments.items(), key=lambda x: x[1]["score"], reverse=True)
        n_coins = len(ranked)
        n_long = max(1, int(n_coins * LONG_PCT))

        top_coins = [r[0] for r in ranked[:n_long] if r[1]["score"] >= MIN_SCORE_TO_BUY]
        bottom_coins = [r[0] for r in ranked[-n_long:] if r[1]["score"] < 0.40]

        self.trader.custom["top_coins"] = top_coins
        self.trader.custom["bottom_coins"] = bottom_coins

        top_str = ", ".join(f"{c}({sentiments[c]['score']:.2f})" for c in top_coins)
        bot_str = ", ".join(f"{c}({sentiments[c]['score']:.2f})" for c in bottom_coins)
        self.trader.append_log("INFO", f"Ranking: LONG={top_str} | SHORT={bot_str}")

        # 4. Close LONG positions in bottom coins or not in top
        for pos in list(self.trader.open_positions):
            sym = pos.get("metadata", {}).get("symbol")
            direction = pos.get("metadata", {}).get("direction", "long")

            # Check min hold time
            opened_at = pos.get("opened_at", "")
            if opened_at:
                try:
                    open_time = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                    hold_h = (datetime.now(timezone.utc) - open_time).total_seconds() / 3600
                    if hold_h < MIN_HOLD_HOURS:
                        continue
                except:
                    pass

            if direction == "long":
                # Close long if sentiment dropped
                coin_sent = sentiments.get(sym, {}).get("score", 0.5)
                if coin_sent < 0.40:
                    price = prices.get(sym, {}).get("price", pos["entry_price"])
                    trade = self.trader.sell(pos["id"], price, reason="SENTIMENT_ROTATION")
                    if trade:
                        rpnl = trade.get("realized_pnl", 0)
                        update_cooldown_on_close(self.trader.custom, pos.get('metadata', {}).get('symbol', ''), pos.get('metadata', {}).get('direction', 'long'), rpnl > 0)
                        score = sentiments.get(sym, {}).get("score", 0)
                        self.trader.append_log("SELL", f"LONG {sym} | PnL: ${rpnl:+.2f} | Sentiment: {score:.2f}")
                        self.trader.custom["trailing_highs"].pop(pos["id"], None)
            elif direction == "short":
                # Close short if sentiment recovered above neutral
                coin_score = sentiments.get(sym, {}).get("score", 0.5)
                if coin_score >= SHORT_EXIT_SCORE:
                    price = prices.get(sym, {}).get("price", pos["entry_price"])
                    entry = pos["entry_price"]
                    trade = self.trader.sell(pos["id"], price, reason="SHORT_SENTIMENT_RECOVERY")
                    if trade:
                        # Recalculate PnL for short
                        real_pnl = (entry - price) / entry * pos["size_usd"]
                        trade["realized_pnl"] = round(real_pnl, 4)
                        rpnl = trade["realized_pnl"]
                        self.trader.append_log(
                            "WIN" if rpnl > 0 else "LOSS",
                            f"CLOSE SHORT {sym} | PnL: ${rpnl:+.2f} | Sentiment recovered: {coin_score:.2f}"
                        )
                        self.trader.custom["trailing_lows"].pop(pos["id"], None)

        # 5. Open LONG positions for top coins
        current_symbols = set(
            p.get("metadata", {}).get("symbol") for p in self.trader.open_positions
        )

        LEVERAGE = 10
        available = self.trader.equity * (1 - CASH_RESERVE_PCT) * LEVERAGE
        per_pos = available / MAX_POSITIONS if MAX_POSITIONS > 0 else 0

        for coin in top_coins:
            if len(self.trader.open_positions) >= MAX_POSITIONS:
                break
            if coin in current_symbols:
                continue
            if coin not in prices or prices[coin]["price"] <= 0:
                continue

            # Size boost on priority coins (ONDO/LINK/APT — 88-94% WR chez Zaid)
            size = per_pos * (BOOST_FACTOR if coin in PRIORITY_COINS else 1.0)
            if size < 5:
                continue
            # FIX 2026-05-10: indentation + macro filter A + blacklist C
            if not long_ok:
                self.trader.append_log('MACRO_BLOCK', f'LONG {coin} blocked - regime not long-friendly')
                continue
            if should_veto_entry(coin, 'long', prices):
                self.trader.append_log('VETO', f'LONG {coin} blocked - strong downtrend')
                continue
            if check_cooldown(self.trader.custom, coin, 'long'):
                self.trader.append_log('COOLDOWN', f'LONG {coin} blocked - 3-loss streak')
                continue
            if _local_check_blacklist(self.trader.custom, coin, 'long'):
                self.trader.append_log('BLACKLIST', f'LONG {coin} blocked - 2-SL blacklist 72h')
                continue
            price = prices[coin]["price"]
            score = sentiments[coin]["score"]
            count = sentiments[coin]["count"]

            pos = self.trader.buy(
                symbol=coin,
                amount_usd=size,
                price=price,
                reason=f"LONG Sentiment: {score:.2f} ({count} articles)",
                metadata={
                    "symbol": coin,
                    "direction": "long",
                    "sentiment_score": score,
                    "article_count": count,
                    "pair": SYMBOL_MAP[coin][2],
                },
            )
            if pos:
                self.trader.custom["trailing_highs"][pos["id"]] = price
                self.trader.append_log("BUY", (
                    f"LONG {coin} @ ${price:.4f} | Size: ${size:.2f} | "
                    f"Sentiment: {score:.2f} ({count} articles)"
                ))

        # 6. LONG-ONLY VERSION — short opening disabled (LO bot)
        self.trader.custom["short_coins"] = []

        # 7. Update state
        self.trader.custom["last_rebalance_ts"] = time.time()
        self.trader.custom["rebalance_count"] += 1

    def run_cycle(self):
        """One cycle."""
        self.trader.tick()

        # Fetch prices
        prices = fetch_prices_cached()
        if not prices:
            self.trader.append_log("WARN", "Failed to fetch prices")
            self.trader.append_equity_point()
            self.trader.save_state()
            return

        # Update positions with current prices
        for pos in self.trader.open_positions:
            sym = pos.get("metadata", {}).get("symbol")
            direction = pos.get("metadata", {}).get("direction", "long")
            if sym and sym in prices:
                current = prices[sym]["price"]
                entry = pos["entry_price"]
                pos["current_price"] = current
                if direction == "short":
                    pos["unrealized_pnl"] = round(
                        (entry - current) / entry * pos["size_usd"], 4
                    )
                else:
                    pos["unrealized_pnl"] = round(
                        (current / entry - 1) * pos["size_usd"], 4
                    )
        self.trader._recalc_equity()

        # Check stops
        self.check_stops(prices)

        # Rebalance if time
        last = self.trader.custom.get("last_rebalance_ts", 0)
        if time.time() - last > REBALANCE_HOURS * 3600:
            self.rebalance(prices)

        self.trader.append_equity_point()
        self.trader.save_state()

        # Refresh dashboard_data.js after each cycle so the HTML dashboard sees us
        try:
            import sys as _sys
            from pathlib import Path as _P
            _root = _P(__file__).resolve().parent.parent.parent  # CRYPTO_BOT_LIVE/
            if str(_root / "bot") not in _sys.path:
                _sys.path.insert(0, str(_root / "bot"))
            from core.dashboard_export import export_dashboard_data
            export_dashboard_data(
                bot_keys=["sentiment_ls_v3_lo", "confluence_reverse", "ultimate_v2_reverse"],
                data_dir=str(_root / "data"),
                dashboard_dir=str(_root / "dashboard"),
            )
        except Exception as _e:
            print(f"[WARN] dashboard export error: {_e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    cfg = BOT_CONFIGS["sentiment_ls_v3_lo"]
    bot = SentimentBot(cfg)

    print("=" * 60)
    print("  SENTIMENT LONG-ONLY V3 ULTRA — 148 SOURCES")
    print(f"  Capital: ${cfg['capital']:.0f} | Universe: {len(UNIVERSE)} coins")
    print(f"  Rebalance: every {REBALANCE_HOURS}h | Max positions: {MAX_POSITIONS}")
    print(f"  LLM: DeepSeek ({DEEPSEEK_MODEL})")
    print(f"  Mode: LONG-ONLY")
    print(f"  Stop-loss: {STOP_LOSS_PCT*100:.0f}% | Trailing: {TRAILING_SL_PCT*100:.0f}%")
    print(f"  Equity: ${bot.trader.equity:.2f}")
    print("=" * 60)

    bot.trader.append_log("INFO", (
        f"Sentiment LO V3 ULTRA started | Capital: ${cfg['capital']:.0f} | "
        f"{len(RSS_FEEDS)} RSS + {len(REDDIT_SUBS)} Reddit | DeepSeek | "
        f"LONG-ONLY mode"
    ))

    # Stagger startup to avoid CoinGecko rate limit (11 bots)
    import random
    startup_delay = random.randint(30, 120)
    print(f'  Waiting {startup_delay}s to stagger CoinGecko calls...')
    time.sleep(startup_delay)

    while True:
        try:
            bot.run_cycle()
        except KeyboardInterrupt:
            print("\nShutting down...")
            bot.trader.append_log("INFO", "Bot stopped by user")
            bot.trader.write_heartbeat("stopped")
            bot.trader.save_state()
            break
        except Exception as e:
            tb = traceback.format_exc()
            bot.trader.append_log("ERROR", f"Cycle error: {e}\n{tb}")
            print(f"[ERROR] {e}")
            time.sleep(60)

        time.sleep(cfg["cycle_seconds"])


if __name__ == "__main__":
    main()
