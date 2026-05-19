# Crypto Bot Live — ENIX Trading Fleet (clone)

Réplique exacte de l'architecture du **TRADING FLEET** observée dans `trading-dashboard-eight-pi.vercel.app`, adaptée pour exécution **LIVE** sur Hyperliquid DEX.

## Stack

- **Exchange :** Hyperliquid (perp DEX, leverage 3x)
- **Wallet :** MetaMask → API wallet dédié
- **LLM sentiment :** DeepSeek (fallback Gemini)
- **News :** CryptoNews + CryptoPanic
- **Hosting bot :** Google Cloud Run (cron 5-15 min via Scheduler)
- **Dashboard :** Vercel (HTML/CSS/JS vanilla, fichier unique)

## Structure (1:1 avec TRADING FLEET observé)

```
crypto-bot-live/
├── bot/
│   ├── main.py                   # Boucle principale + cycle orchestrator
│   ├── bots/
│   │   ├── base_bot.py           # Classe abstraite (entry/exit/MAX_HOLD/exit_band/SL/TP)
│   │   └── sentiment_v1.py       # Premier bot : LINK+SUI+INJ multi-crypto
│   └── core/
│       ├── hyperliquid_client.py # Wrapper SDK officiel (testnet+mainnet)
│       ├── paper_trader.py       # Mode paper (fallback / dev)
│       ├── news_feed.py          # CryptoNews + CryptoPanic
│       ├── sentiment.py          # DeepSeek (fallback Gemini)
│       ├── state.py              # Persistence state.json/equity.json/heartbeat
│       └── kill_switch.py        # Drawdown -15% → STOP
├── dashboard/
│   ├── index.html                # Clone trading-dashboard-eight-pi
│   └── api/data.js               # Vercel function lit JSON depuis Cloud Storage
├── data/                         # JSON files (state, equity, heartbeat)
├── scripts/
│   ├── deploy_cloud_run.sh
│   └── deploy_dashboard.sh
├── tests/
│   └── test_hyperliquid_testnet.py
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Convention de nommage des bots (identique à observé)

- `sentiment_<strat>` → bot décision LLM
- `<asset>_v<N>` → bot mono-asset

## Paramètres validés en prod (depuis paper bot)

| Param | Valeur |
|---|---|
| `MAX_HOLD_HOURS` (standard) | 72 |
| `MAX_HOLD_HOURS` (scalp) | 24 |
| `EXIT_BAND_PCT` (standard) | 0.01 |
| `EXIT_BAND_PCT` (scalp) | 0.005 |
| `TP_PCT` | 0.05 |
| `SL_PCT` | -0.08 |
| `TRAILING_PCT` | 0.03 |
| `VETO_PCT` | 0.03 |
| `COOLDOWN_AFTER_3_LOSSES_HOURS` | 48 |
| `MAX_POSITIONS` | 8 |
| `LEVERAGE` | **3** (live conservateur, paper était 10) |
| `KILL_SWITCH_DD_PCT` | -0.15 |

## Seuils sentiment

- LONG : score ≥ 0.65
- SHORT : score ≤ 0.40
- NEUTRAL : 0.40 < score < 0.65

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure (testnet first!)
cp .env.example .env
# Édite .env avec :
# HYPERLIQUID_PRIVATE_KEY=0x...     (API wallet, pas MetaMask seed)
# HYPERLIQUID_NETWORK=testnet        (ou mainnet)
# DEEPSEEK_API_KEY=sk-...
# CRYPTONEWS_API_KEY=...

# 3. Test connection
python -m bot.core.hyperliquid_client --check

# 4. Run bot (mode paper d'abord)
python -m bot.main --mode paper

# 5. Run bot live (testnet HL)
python -m bot.main --mode live --network testnet

# 6. Run bot live (MAINNET — vrai argent)
python -m bot.main --mode live --network mainnet
```
