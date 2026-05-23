@echo off
chcp 65001 >nul
title Deploy Fleet Zaid (LS V3 LO + Confluence Rev + Ultimate V2 Rev)

echo ================================================================
echo   DEPLOIEMENT FLEET ZAID — 3 bots reverse-engineered
echo   Capital TOTAL : $1000 paper (333 / 333 / 333)
echo ================================================================
echo.

cd /d C:\enix-bot\crypto-bot-live

echo [1/5] Recuperation du code a jour (git pull)...
git pull
echo.

echo [2/5] Installation des dependances Python...
python -m pip install --quiet --upgrade requests python-dotenv
echo   OK.
echo.

echo [3/5] Arret des anciennes taches + reset des state files...
schtasks /End /TN EnixCryptoBotLO 2>nul | Out-Null
schtasks /End /TN EnixCryptoBotConfRev 2>nul | Out-Null
schtasks /End /TN EnixCryptoBotUltRev 2>nul | Out-Null
timeout /t 2 /nobreak >nul

REM Supprime les state des 3 bots Zaid (capital change : $10k -> $333) — les autres bots existants INTACTS
del /Q data\sentiment_ls_v3_lo_state.json 2>nul
del /Q data\sentiment_ls_v3_lo_equity.json 2>nul
del /Q data\sentiment_ls_v3_lo_log.json 2>nul
del /Q data\heartbeat_sentiment_ls_v3_lo.json 2>nul
del /Q data\confluence_reverse_state.json 2>nul
del /Q data\confluence_reverse_equity.json 2>nul
del /Q data\confluence_reverse_log.json 2>nul
del /Q data\heartbeat_confluence_reverse.json 2>nul
del /Q data\ultimate_v2_reverse_state.json 2>nul
del /Q data\ultimate_v2_reverse_equity.json 2>nul
del /Q data\ultimate_v2_reverse_log.json 2>nul
del /Q data\heartbeat_ultimate_v2_reverse.json 2>nul
echo   OK reset (autres bots data preserves).
echo.

echo [4/5] Creation/relance des 3 taches planifiees Fleet Zaid...
powershell -ExecutionPolicy Bypass -File .\setup_tasks_fleet_zaid.ps1
echo.

echo [5/5] Verification du statut des 3 bots...
timeout /t 3 /nobreak >nul
schtasks /Query /TN EnixCryptoBotLO 2>nul | findstr /v "^$"
schtasks /Query /TN EnixCryptoBotConfRev 2>nul | findstr /v "^$"
schtasks /Query /TN EnixCryptoBotUltRev 2>nul | findstr /v "^$"
echo.

echo ================================================================
echo   TERMINE - 3 bots Fleet Zaid tournent 24/7 ($1000 paper total)
echo ================================================================
echo.
echo   sentiment_ls_v3_lo  : $333 - Long-Only V3 + 4 patches
echo   confluence_reverse  : $333 - Multi-signal composite score
echo   ultimate_v2_reverse : $333 - Triple signal conviction haute
echo.
echo Tu peux fermer cette fenetre et le RDP, les bots tournent 24/7.
echo.
pause
