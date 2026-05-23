@echo off
chcp 65001 >nul
title Mise a jour du bot LS V3 LO (auto)

echo ================================================================
echo   MISE A JOUR AUTOMATIQUE DU BOT LS V3 LO
echo ================================================================
echo.

cd /d C:\enix-bot\crypto-bot-live

echo [1/4] Recuperation du code a jour (git pull)...
git pull
echo.

echo [2/4] Installation des dependances Python...
python -m pip install --quiet --upgrade requests python-dotenv
echo   OK.
echo.

echo [3/4] Creation/mise a jour de la tache planifiee EnixCryptoBotLO...
powershell -ExecutionPolicy Bypass -File .\setup_task_lsv3lo.ps1
echo.

echo [4/4] Verification du statut...
timeout /t 3 /nobreak >nul
schtasks /Query /TN EnixCryptoBotLO 2>nul
echo.

echo ================================================================
echo   TERMINE - le bot LS V3 LO ENIX BOOSTED tourne maintenant 24/7
echo ================================================================
echo.
echo Pour voir les logs en direct, tape (depuis ce dossier) :
echo   Get-Content data\sentiment_ls_v3_lo_log.json -Wait -Tail 20
echo.
echo Tu peux fermer cette fenetre et le RDP, le bot tourne sur le VPS.
echo.
pause
