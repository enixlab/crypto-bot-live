@echo off
cd /d C:\enix-bot\crypto-bot-live
:loop
echo. >> bot.log
echo ============================================== >> bot.log
echo  ENIX CRYPTO BOT - %DATE% %TIME% >> bot.log
echo ============================================== >> bot.log
python -m bot.main --mode paper >> bot.log 2>&1
echo Bot stopped. Restart in 30s... >> bot.log
timeout /t 30 /nobreak
goto loop
