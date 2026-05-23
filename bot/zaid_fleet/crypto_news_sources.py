"""
CRYPTO NEWS SOURCES - Liste exhaustive de 130+ sources gratuites testees
Genere le 2026-03-25
Chaque source a ete testee via curl et retourne HTTP 200
"""

# =============================================================================
# SECTION 1: RSS FEEDS - SITES CRYPTO MAJEURS (55 sources)
# =============================================================================
RSS_FEEDS = {
    # --- Tier 1 : Sites majeurs, mise a jour toutes les heures ---
    "cointelegraph": {
        "url": "https://cointelegraph.com/rss",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 30,
        "weight": 3,  # Poids pour le sentiment (1-3)
    },
    "cointelegraph_analysis": {
        "url": "https://cointelegraph.com/rss/category/analysis",
        "type": "analysis",
        "frequency": "daily",
        "items_per_fetch": 30,
        "weight": 3,
    },
    "cointelegraph_market": {
        "url": "https://cointelegraph.com/rss/category/market-analysis",
        "type": "analysis",
        "frequency": "daily",
        "items_per_fetch": 30,
        "weight": 3,
    },
    "cointelegraph_regulation": {
        "url": "https://cointelegraph.com/rss/category/regulation",
        "type": "regulation",
        "frequency": "daily",
        "items_per_fetch": 2,
        "weight": 2,
    },
    "cointelegraph_bitcoin": {
        "url": "https://cointelegraph.com/rss/tag/bitcoin",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 30,
        "weight": 3,
    },
    "cointelegraph_ethereum": {
        "url": "https://cointelegraph.com/rss/tag/ethereum",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 30,
        "weight": 2,
    },
    "cointelegraph_defi": {
        "url": "https://cointelegraph.com/rss/tag/defi",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 30,
        "weight": 2,
    },
    "cointelegraph_weekly": {
        "url": "https://cointelegraph.com/rss/category/weekly-overview",
        "type": "analysis",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "coindesk": {
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 25,
        "weight": 3,
    },
    "decrypt": {
        "url": "https://decrypt.co/feed",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 36,
        "weight": 3,
    },
    "the_block": {
        "url": "https://www.theblock.co/rss.xml",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 20,
        "weight": 3,
    },
    "bitcoin_magazine": {
        "url": "https://bitcoinmagazine.com/.rss/full/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 3,
    },
    "blockworks": {
        "url": "https://blockworks.co/feed",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 50,
        "weight": 3,
    },

    # --- Tier 2 : Sites importants, MAJ quotidienne ---
    "cryptopotato": {
        "url": "https://cryptopotato.com/feed/",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 36,
        "weight": 2,
    },
    "cryptobriefing": {
        "url": "https://cryptobriefing.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 30,
        "weight": 2,
    },
    "u_today": {
        "url": "https://u.today/rss",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 95,
        "weight": 2,
    },
    "ambcrypto": {
        "url": "https://ambcrypto.com/feed/",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 16,
        "weight": 2,
    },
    "daily_hodl": {
        "url": "https://dailyhodl.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "newsbtc": {
        "url": "https://newsbtc.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "bitcoinist": {
        "url": "https://bitcoinist.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 8,
        "weight": 2,
    },
    "coingape": {
        "url": "https://coingape.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 20,
        "weight": 2,
    },
    "cryptonews": {
        "url": "https://cryptonews.com/news/feed/",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 20,
        "weight": 2,
    },
    "blockonomi": {
        "url": "https://blockonomi.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "zycrypto": {
        "url": "https://zycrypto.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 14,
        "weight": 2,
    },
    "the_defiant": {
        "url": "https://thedefiant.io/feed",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 100,
        "weight": 3,
    },
    "crypto_news_2": {
        "url": "https://crypto.news/feed/",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 50,
        "weight": 2,
    },
    "dl_news": {
        "url": "https://www.dlnews.com/arc/outboundfeeds/rss/",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 100,
        "weight": 3,
    },

    # --- Tier 3 : Sites secondaires ---
    "thecryptobasic": {
        "url": "https://thecryptobasic.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "cryptodaily": {
        "url": "https://cryptodaily.co.uk/feed",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 200,
        "weight": 1,
    },
    "coinjournal": {
        "url": "https://coinjournal.net/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 9,
        "weight": 1,
    },
    "cryptoglobe": {
        "url": "https://www.cryptoglobe.com/latest/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "coinspeaker": {
        "url": "https://www.coinspeaker.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "cryptopanic": {
        "url": "https://cryptopanic.com/news/rss/",
        "type": "aggregator",
        "frequency": "hourly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "unchained": {
        "url": "https://unchainedcrypto.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "messari": {
        "url": "https://messari.io/rss",
        "type": "analysis",
        "frequency": "daily",
        "items_per_fetch": 15,
        "weight": 3,
    },
    "protos": {
        "url": "https://protos.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "watcher_guru": {
        "url": "https://watcher.guru/news/feed",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "finbold": {
        "url": "https://finbold.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 11,
        "weight": 1,
    },
    "cryptopolitan": {
        "url": "https://www.cryptopolitan.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "coinpedia": {
        "url": "https://coinpedia.org/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "tokenist": {
        "url": "https://tokenist.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "nft_evening": {
        "url": "https://nftevening.com/feed/",
        "type": "nft",
        "frequency": "daily",
        "items_per_fetch": 123,
        "weight": 1,
    },
    "web3_is_going_great": {
        "url": "https://web3isgoinggreat.com/feed.xml",
        "type": "news",
        "frequency": "weekly",
        "items_per_fetch": 20,
        "weight": 1,
    },
    "defiprime": {
        "url": "https://defiprime.com/feed.xml",
        "type": "defi",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "defi_rate": {
        "url": "https://defirate.com/feed/",
        "type": "defi",
        "frequency": "weekly",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "fxstreet_crypto": {
        "url": "https://www.fxstreet.com/cryptocurrencies/news/feed",
        "type": "analysis",
        "frequency": "hourly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "investing_com_crypto": {
        "url": "https://www.investing.com/rss/news_301.rss",
        "type": "news",
        "frequency": "hourly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "bloomberg_crypto": {
        "url": "https://feeds.bloomberg.com/crypto/news.rss",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 3,
    },
    "techcrunch_crypto": {
        "url": "https://techcrunch.com/category/cryptocurrency/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 20,
        "weight": 2,
    },
    "nulltx": {
        "url": "https://nulltx.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "altcoinbuzz": {
        "url": "https://www.altcoinbuzz.io/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "trustnodes": {
        "url": "https://www.trustnodes.com/feed",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 20,
        "weight": 1,
    },
    "forkast_news": {
        "url": "https://forkast.news/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "currency_analytics": {
        "url": "https://thecurrencyanalytics.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 25,
        "weight": 1,
    },
    "thebitcoinnews": {
        "url": "https://thebitcoinnews.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 25,
        "weight": 1,
    },
    "bitcoinworld": {
        "url": "https://bitcoinworld.co.in/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "coincu": {
        "url": "https://www.coincu.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "cryptoadventure": {
        "url": "https://cryptoadventure.com/feed/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 9,
        "weight": 1,
    },
    "blockchain_news": {
        "url": "https://blockchain.news/RSS/",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "coinlive": {
        "url": "https://www.coinlive.com/feed",
        "type": "news",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
}

# =============================================================================
# SECTION 2: BLOGS & RECHERCHE (17 sources)
# =============================================================================
RESEARCH_FEEDS = {
    "chainalysis_blog": {
        "url": "https://blog.chainalysis.com/feed/",
        "type": "research",
        "frequency": "weekly",
        "items_per_fetch": 10,
        "weight": 3,
    },
    "kraken_blog": {
        "url": "https://blog.kraken.com/feed/",
        "type": "exchange_blog",
        "frequency": "weekly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "vitalik_blog": {
        "url": "https://vitalik.eth.limo/feed.xml",
        "type": "research",
        "frequency": "monthly",
        "items_per_fetch": 170,
        "weight": 3,
    },
    "ethereum_foundation": {
        "url": "https://blog.ethereum.org/feed.xml",
        "type": "research",
        "frequency": "weekly",
        "items_per_fetch": 619,
        "weight": 3,
    },
    "bitcoin_optech": {
        "url": "https://bitcoinops.org/feed.xml",
        "type": "research",
        "frequency": "weekly",
        "items_per_fetch": 50,
        "weight": 3,
    },
    "glassnode_insights": {
        "url": "https://insights.glassnode.com/rss/",
        "type": "on_chain_analysis",
        "frequency": "weekly",
        "items_per_fetch": 9,
        "weight": 3,
    },
    "deribit_insights": {
        "url": "https://deribit.com/insights/feed",
        "type": "derivatives_analysis",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 3,
    },
    "galaxy_research": {
        "url": "https://www.galaxy.com/research/feed.xml",
        "type": "research",
        "frequency": "weekly",
        "items_per_fetch": 20,
        "weight": 3,
    },
    "chainlink_blog": {
        "url": "https://blog.chain.link/feed/",
        "type": "research",
        "frequency": "weekly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "pantera_capital": {
        "url": "https://panteracapital.com/feed/",
        "type": "research",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 3,
    },
    "btcpeers": {
        "url": "https://btcpeers.com/rss/",
        "type": "research",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    # Forums techniques
    "ethereum_magicians": {
        "url": "https://ethereum-magicians.org/latest.rss",
        "type": "technical_forum",
        "frequency": "daily",
        "items_per_fetch": 30,
        "weight": 2,
    },
    "ethresearch": {
        "url": "https://ethresear.ch/latest.rss",
        "type": "technical_forum",
        "frequency": "daily",
        "items_per_fetch": 30,
        "weight": 2,
    },
    "makerdao_forum": {
        "url": "https://forum.makerdao.com/latest.rss",
        "type": "governance_forum",
        "frequency": "daily",
        "items_per_fetch": 30,
        "weight": 2,
    },
}

# =============================================================================
# SECTION 3: MEDIUM PUBLICATIONS (13 sources)
# =============================================================================
MEDIUM_FEEDS = {
    "coinmonks": {
        "url": "https://medium.com/feed/coinmonks",
        "type": "analysis",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "the_capital": {
        "url": "https://medium.com/feed/the-capital",
        "type": "analysis",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "vitalik_medium": {
        "url": "https://medium.com/feed/@VitalikButerin",
        "type": "research",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 3,
    },
    "binance_medium": {
        "url": "https://medium.com/feed/@binance",
        "type": "exchange_blog",
        "frequency": "weekly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "mycrypto": {
        "url": "https://medium.com/feed/mycrypto",
        "type": "education",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "aave_medium": {
        "url": "https://medium.com/feed/aave",
        "type": "defi",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "uniswap_medium": {
        "url": "https://medium.com/feed/uniswap",
        "type": "defi",
        "frequency": "monthly",
        "items_per_fetch": 3,
        "weight": 2,
    },
    "1inch_medium": {
        "url": "https://medium.com/feed/1inch-network",
        "type": "defi",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 1,
    },
    "chainlink_medium": {
        "url": "https://medium.com/feed/chainlink-community",
        "type": "research",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "dragonfly_research": {
        "url": "https://medium.com/feed/dragonfly-research",
        "type": "research",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 3,
    },
    "amber_group": {
        "url": "https://medium.com/feed/amber-group",
        "type": "research",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "nansen_medium": {
        "url": "https://medium.com/feed/nansen-ai",
        "type": "on_chain_analysis",
        "frequency": "monthly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "token_terminal": {
        "url": "https://medium.com/feed/token-terminal",
        "type": "analysis",
        "frequency": "monthly",
        "items_per_fetch": 10,
        "weight": 2,
    },
}

# =============================================================================
# SECTION 4: SUBSTACK NEWSLETTERS (14 sources)
# =============================================================================
SUBSTACK_FEEDS = {
    "0x_research": {
        "url": "https://0xresearch.substack.com/feed",
        "type": "research",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 3,
    },
    "the_daily_gwei": {
        "url": "https://thedailygwei.substack.com/feed",
        "type": "analysis",
        "frequency": "daily",
        "items_per_fetch": 10,
        "weight": 2,
    },
    "arthur_hayes": {
        "url": "https://cryptohayes.substack.com/feed",
        "type": "analysis",
        "frequency": "monthly",
        "items_per_fetch": 5,
        "weight": 3,
    },
    "dirt_roads": {
        "url": "https://dirtroads.substack.com/feed",
        "type": "research",
        "frequency": "monthly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "wrong_a_lot": {
        "url": "https://wrongalot.substack.com/feed",
        "type": "analysis",
        "frequency": "monthly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "cobie": {
        "url": "https://cobie.substack.com/feed",
        "type": "analysis",
        "frequency": "monthly",
        "items_per_fetch": 5,
        "weight": 3,
    },
    "dose_of_defi": {
        "url": "https://doseofdefi.substack.com/feed",
        "type": "defi",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "our_network": {
        "url": "https://ournetwork.substack.com/feed",
        "type": "on_chain_analysis",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 3,
    },
    "the_defi_edge": {
        "url": "https://thedefiedge.substack.com/feed",
        "type": "defi",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "defi_education": {
        "url": "https://defieducation.substack.com/feed",
        "type": "education",
        "frequency": "weekly",
        "items_per_fetch": 14,
        "weight": 1,
    },
    "kerman_kohli": {
        "url": "https://kermankohli.substack.com/feed",
        "type": "defi",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "jarvislabs": {
        "url": "https://jarvislabs.substack.com/feed",
        "type": "analysis",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "defi_daily": {
        "url": "https://defi-daily.substack.com/feed",
        "type": "defi",
        "frequency": "daily",
        "items_per_fetch": 5,
        "weight": 1,
    },
    "token_insight_sub": {
        "url": "https://tokeninsight.substack.com/feed",
        "type": "analysis",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "block_threat": {
        "url": "https://newsletter.blockthreat.io/feed",
        "type": "security",
        "frequency": "weekly",
        "items_per_fetch": 5,
        "weight": 2,
    },
    "ryan_watkins": {
        "url": "https://ryanwatkins.substack.com/feed",
        "type": "research",
        "frequency": "monthly",
        "items_per_fetch": 5,
        "weight": 2,
    },
}

# =============================================================================
# SECTION 5: REDDIT SUBREDDITS - JSON API (25 sources)
# Endpoint: https://www.reddit.com/r/{sub}/top/.json?t=day&limit=25
# IMPORTANT: Utiliser User-Agent browser, sinon 403
# =============================================================================
REDDIT_FEEDS = {
    "r_cryptocurrency": {
        "url": "https://www.reddit.com/r/cryptocurrency/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 3,
    },
    "r_bitcoin": {
        "url": "https://www.reddit.com/r/bitcoin/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 3,
    },
    "r_ethereum": {
        "url": "https://www.reddit.com/r/ethereum/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 3,
    },
    "r_defi": {
        "url": "https://www.reddit.com/r/defi/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 2,
    },
    "r_cryptomarkets": {
        "url": "https://www.reddit.com/r/CryptoMarkets/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 2,
    },
    "r_altcoin": {
        "url": "https://www.reddit.com/r/altcoin/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_binance": {
        "url": "https://www.reddit.com/r/binance/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_solana": {
        "url": "https://www.reddit.com/r/solana/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 2,
    },
    "r_cardano": {
        "url": "https://www.reddit.com/r/cardano/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_chainlink": {
        "url": "https://www.reddit.com/r/Chainlink/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_polkadot": {
        "url": "https://www.reddit.com/r/polkadot/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_cosmosnetwork": {
        "url": "https://www.reddit.com/r/cosmosnetwork/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_avax": {
        "url": "https://www.reddit.com/r/avax/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_ripple": {
        "url": "https://www.reddit.com/r/Ripple/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_litecoin": {
        "url": "https://www.reddit.com/r/litecoin/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_dogecoin": {
        "url": "https://www.reddit.com/r/dogecoin/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_satoshistreetbets": {
        "url": "https://www.reddit.com/r/SatoshiStreetBets/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 2,
    },
    "r_bitcoinmarkets": {
        "url": "https://www.reddit.com/r/BitcoinMarkets/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 3,
    },
    "r_ethtrader": {
        "url": "https://www.reddit.com/r/ethtrader/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 2,
    },
    "r_cryptotechnology": {
        "url": "https://www.reddit.com/r/CryptoTechnology/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 2,
    },
    "r_nft": {
        "url": "https://www.reddit.com/r/NFT/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_arbitrum": {
        "url": "https://www.reddit.com/r/arbitrum/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_polygon": {
        "url": "https://www.reddit.com/r/0xPolygon/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_uniswap": {
        "url": "https://www.reddit.com/r/UniSwap/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
    "r_aave": {
        "url": "https://www.reddit.com/r/Aave/top/.json?t=day&limit=25",
        "type": "social",
        "frequency": "realtime",
        "weight": 1,
    },
}

# =============================================================================
# SECTION 6: YOUTUBE CHANNELS RSS (3 sources confirmees)
# Format: https://www.youtube.com/feeds/videos.xml?channel_id=XXXX
# Note: Beaucoup de channel IDs ont change, seuls ceux testes OK sont listes
# =============================================================================
YOUTUBE_FEEDS = {
    "cryptojebb": {
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCu7Sre5A1NMV8J3s2FhluCw",
        "type": "video",
        "frequency": "daily",
        "items_per_fetch": 15,
        "weight": 1,
    },
    "sheldon_evans": {
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCLnQ34ZBSjy2JQjeRudFEDw",
        "type": "video",
        "frequency": "daily",
        "items_per_fetch": 15,
        "weight": 1,
    },
    "cryptowendyo": {
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCN9Nj4tjXbVTLYWN0EKly_Q",
        "type": "video",
        "frequency": "daily",
        "items_per_fetch": 15,
        "weight": 1,
    },
}

# =============================================================================
# SECTION 7: APIs GRATUITES - NEWS & SENTIMENT (17 sources)
# =============================================================================
FREE_APIS = {
    # --- Sentiment ---
    "fear_greed_index": {
        "url": "https://api.alternative.me/fng/?limit=10",
        "type": "sentiment",
        "frequency": "daily",
        "description": "Crypto Fear & Greed Index (0-100)",
        "weight": 3,
    },

    # --- News ---
    "cryptocompare_news": {
        "url": "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&limit=50",
        "type": "news_api",
        "frequency": "hourly",
        "description": "Aggregated crypto news from multiple sources",
        "weight": 3,
    },

    # --- Market Data (utile pour contexte sentiment) ---
    "coingecko_trending": {
        "url": "https://api.coingecko.com/api/v3/search/trending",
        "type": "trending",
        "frequency": "hourly",
        "description": "Top 7 trending coins on CoinGecko",
        "weight": 2,
    },
    "coingecko_btc": {
        "url": "https://api.coingecko.com/api/v3/coins/bitcoin",
        "type": "market_data",
        "frequency": "5min",
        "description": "Bitcoin full data (price, volume, sentiment scores)",
        "weight": 3,
    },
    "coingecko_global": {
        "url": "https://api.coingecko.com/api/v3/global",
        "type": "market_data",
        "frequency": "5min",
        "description": "Global crypto market cap, dominance, volume",
        "weight": 3,
    },
    "coinpaprika_btc": {
        "url": "https://api.coinpaprika.com/v1/coins/btc-bitcoin",
        "type": "market_data",
        "frequency": "5min",
        "description": "Bitcoin data from CoinPaprika",
        "weight": 2,
    },
    "coinpaprika_global": {
        "url": "https://api.coinpaprika.com/v1/global",
        "type": "market_data",
        "frequency": "5min",
        "description": "Global market stats",
        "weight": 2,
    },
    "coinpaprika_tickers": {
        "url": "https://api.coinpaprika.com/v1/tickers",
        "type": "market_data",
        "frequency": "5min",
        "description": "All coin tickers with price changes",
        "weight": 2,
    },
    "coinlore_global": {
        "url": "https://api.coinlore.net/api/global/",
        "type": "market_data",
        "frequency": "5min",
        "description": "Global crypto stats",
        "weight": 1,
    },
    "coinlore_tickers": {
        "url": "https://api.coinlore.net/api/tickers/",
        "type": "market_data",
        "frequency": "5min",
        "description": "Top 100 coins",
        "weight": 1,
    },

    # --- On-chain & Blockchain ---
    "blockcypher_btc": {
        "url": "https://api.blockcypher.com/v1/btc/main",
        "type": "on_chain",
        "frequency": "realtime",
        "description": "BTC blockchain stats (height, unconfirmed, fees)",
        "weight": 2,
    },
    "mempool_fees": {
        "url": "https://mempool.space/api/v1/fees/recommended",
        "type": "on_chain",
        "frequency": "realtime",
        "description": "Bitcoin recommended fees",
        "weight": 2,
    },
    "mempool_hashrate": {
        "url": "https://mempool.space/api/v1/mining/hashrate/3d",
        "type": "on_chain",
        "frequency": "daily",
        "description": "Bitcoin mining hashrate 3 days",
        "weight": 2,
    },
    "blockchain_info_stats": {
        "url": "https://api.blockchain.info/stats",
        "type": "on_chain",
        "frequency": "daily",
        "description": "Bitcoin network stats",
        "weight": 2,
    },
    "etherscan_gas": {
        "url": "https://api.etherscan.io/api?module=gastracker&action=gasoracle",
        "type": "on_chain",
        "frequency": "realtime",
        "description": "Ethereum gas prices",
        "weight": 2,
    },

    # --- DeFi ---
    "defillama_protocols": {
        "url": "https://api.llama.fi/protocols",
        "type": "defi",
        "frequency": "daily",
        "description": "All DeFi protocols with TVL",
        "weight": 3,
    },
    "defillama_historical_tvl": {
        "url": "https://api.llama.fi/v2/historicalChainTvl",
        "type": "defi",
        "frequency": "daily",
        "description": "Historical chain TVL",
        "weight": 2,
    },
}

# =============================================================================
# HELPER: Get all feeds as flat list
# =============================================================================
def get_all_sources():
    """Retourne toutes les sources dans une liste plate."""
    all_sources = {}
    for category, feeds in [
        ("rss", RSS_FEEDS),
        ("research", RESEARCH_FEEDS),
        ("medium", MEDIUM_FEEDS),
        ("substack", SUBSTACK_FEEDS),
        ("reddit", REDDIT_FEEDS),
        ("youtube", YOUTUBE_FEEDS),
        ("api", FREE_APIS),
    ]:
        for name, config in feeds.items():
            all_sources[f"{category}_{name}"] = {**config, "category": category}
    return all_sources


def get_stats():
    """Affiche les stats des sources."""
    categories = {
        "RSS News Sites": len(RSS_FEEDS),
        "Research & Blogs": len(RESEARCH_FEEDS),
        "Medium Publications": len(MEDIUM_FEEDS),
        "Substack Newsletters": len(SUBSTACK_FEEDS),
        "Reddit Subreddits (JSON)": len(REDDIT_FEEDS),
        "YouTube Channels": len(YOUTUBE_FEEDS),
        "Free APIs (news/sentiment/data)": len(FREE_APIS),
    }
    total = sum(categories.values())
    print(f"\n{'='*60}")
    print(f"  CRYPTO NEWS SOURCES - {total} sources totales")
    print(f"{'='*60}")
    for cat, count in categories.items():
        print(f"  {cat:.<45} {count:>3}")
    print(f"{'='*60}")
    print(f"  TOTAL {'.'*38} {total:>3}")
    print(f"{'='*60}\n")
    return total


if __name__ == "__main__":
    get_stats()
    all_src = get_all_sources()
    # Types de contenu
    types = {}
    for s in all_src.values():
        t = s.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
    print("Par type de contenu:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t:.<35} {c:>3}")
