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
powershell -ExecutionPolicy Bypass -Command ^
  "$action = New-ScheduledTaskAction -Execute 'python' -Argument 'bot\zaid_fleet\sentiment_ls_v3_lo.py' -WorkingDirectory 'C:\enix-bot\crypto-bot-live'; ^
   $trigger = New-ScheduledTaskTrigger -AtStartup; ^
   $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest; ^
   $settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1); ^
   Register-ScheduledTask -TaskName 'EnixCryptoBotLO' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null; ^
   schtasks /End /TN EnixCryptoBotLO 2>$null | Out-Null; ^
   Start-Sleep -Seconds 2; ^
   schtasks /Run /TN EnixCryptoBotLO | Out-Null; ^
   Write-Host '  OK. Bot lance.' -ForegroundColor Green"
echo.

echo [4/4] Verification du statut...
timeout /t 3 /nobreak >nul
schtasks /Query /TN EnixCryptoBotLO 2>nul
echo.

echo ================================================================
echo   TERMINE — le bot LS V3 LO ENIX BOOSTED tourne maintenant 24/7
echo ================================================================
echo.
echo Pour voir les logs en direct, tape :
echo   Get-Content C:\enix-bot\crypto-bot-live\data\sentiment_ls_v3_lo_log.json -Wait -Tail 20
echo.
echo Tu peux maintenant fermer cette fenetre et le RDP.
echo Le bot continue de tourner sur le VPS H24.
echo.
pause
