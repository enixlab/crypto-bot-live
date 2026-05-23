@echo off
chcp 65001 >nul
title LS V3 LO - Bot Crypto Long-Only (fix Zaid 22/05/26)

cd /d "%~dp0"

echo ================================================================
echo   LS V3 LO - Sentiment Long-Only V3 Ultra (148 sources)
echo   Capital paper: $10,000  ^|  Leverage: 10x  ^|  Cycle: 5min
echo   19 cryptos  ^|  Rebalance toutes les 4h  ^|  DeepSeek scoring
echo   Circuit breaker: BTC -3%%/24h ou -2%%/4h -^> STRESS mode
echo ================================================================
echo.

REM Python check
where python >nul 2>nul
if errorlevel 1 (
  echo [ERREUR] Python introuvable. Installe Python 3.10+ depuis python.org
  pause
  exit /b 1
)

REM Install deps (idempotent)
echo [INFO] Verification des dependances...
python -m pip install --quiet --upgrade requests python-dotenv

echo.
echo [INFO] Lancement du bot LS V3 LO...
echo        State files vers : %CD%\data\sentiment_ls_v3_lo_*.json
echo        Dashboard         : double-clique sur dashboard\index.html
echo        Ctrl+C pour arreter (etat sauvegarde a chaque cycle)
echo.

cd bot\zaid_fleet
python sentiment_ls_v3_lo.py

pause
