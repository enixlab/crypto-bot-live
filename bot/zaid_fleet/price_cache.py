"""Shared price cache to avoid CoinGecko rate limiting with 11 bots."""
import json
import os
import time
import requests

_data_dir = os.environ.get("PAPER_DATA_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
os.makedirs(_data_dir, exist_ok=True)
CACHE_FILE = os.path.join(_data_dir, "price_cache.json")
CACHE_TTL = 120  # 2 minutes
COINGECKO_API = "https://api.coingecko.com/api/v3"

ALL_IDS = "bitcoin,ethereum,solana,ripple,cardano,avalanche-2,polkadot,chainlink,uniswap,near,aptos,arbitrum,optimism,dogecoin,fetch-ai,render-token,sui,aave,filecoin,ondo-finance,bittensor,ocean-protocol,theta-token,helium,akash-network,shiba-inu,pepe,bonk,immutable-x,axie-infinity,gala,illuvium,lido-dao,maker,polygon-ecosystem-token,starknet"


def get_cached_prices():
    """Get prices from cache or fetch fresh."""
    # Try cache first
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
            if time.time() - cache.get("_ts", 0) < CACHE_TTL:
                return cache.get("prices", {})
        except:
            pass

    # Fetch fresh
    for attempt in range(3):
        try:
            r = requests.get(f"{COINGECKO_API}/simple/price", params={
                "ids": ALL_IDS,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
            }, timeout=15)
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            prices = {}
            for cid, d in data.items():
                prices[cid] = {
                    "price": d.get("usd", 0),
                    "change_24h": d.get("usd_24h_change", 0),
                    "volume_24h": d.get("usd_24h_vol", 0),
                }
            # Save cache
            try:
                with open(CACHE_FILE, "w") as f:
                    json.dump({"_ts": time.time(), "prices": prices}, f)
            except:
                pass
            return prices
        except:
            time.sleep(10)

    # Last resort: return stale cache
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE)).get("prices", {})
        except:
            pass
    return {}
