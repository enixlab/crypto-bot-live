@echo off
chcp 65001 >nul
title STATUS Fleet Zaid

cd /d C:\enix-bot\crypto-bot-live

echo ================================================================
echo   STATUS — Fleet Zaid (3 bots)
echo ================================================================
echo.

powershell -ExecutionPolicy Bypass -File .\show_status.ps1

echo.
echo Retape  .\STATUS.bat  pour rafraichir
echo Logs live :  Get-Content data\sentiment_ls_v3_lo_log.json -Wait -Tail 20
echo.
pause
