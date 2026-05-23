@echo off
chcp 65001 >nul
title STATUS Fleet Zaid

cd /d C:\enix-bot\crypto-bot-live

echo ================================================================
echo   STATUS — Fleet Zaid (3 bots)
echo ================================================================
echo.

powershell -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem data\sentiment_ls_v3_lo_state.json, data\confluence_reverse_state.json, data\ultimate_v2_reverse_state.json -ErrorAction SilentlyContinue | ForEach-Object { ^
     $bot = Get-Content $_ -Raw | ConvertFrom-Json; ^
     $eq = [math]::Round($bot.equity, 2); ^
     $init = [math]::Round($bot.initial_capital, 2); ^
     $pnl = [math]::Round($eq - $init, 2); ^
     $pct = if ($init -gt 0) { [math]::Round(($pnl / $init) * 100, 2) } else { 0 }; ^
     $color = if ($pnl -ge 0) { 'Green' } else { 'Red' }; ^
     Write-Host ''; ^
     Write-Host '=== ' -NoNewline; Write-Host $bot.bot_id -ForegroundColor Cyan; ^
     Write-Host ('  Equity      : $' + $eq + '  (init $' + $init + ')'); ^
     Write-Host ('  PnL         : $' + $pnl + ' (' + $pct + '%)') -ForegroundColor $color; ^
     Write-Host ('  Positions   : ' + $bot.open_positions.Count + ' open / ' + $bot.closed_trades.Count + ' closed'); ^
     Write-Host ('  Cycles      : ' + $bot.cycle_count); ^
     Write-Host ('  Last cycle  : ' + $bot.last_cycle); ^
     Write-Host ('  Regime      : ' + $bot.custom.macro_regime + ' | F&G=' + $bot.custom.fear_greed + ' | Stress=' + $bot.custom.stress_mode); ^
     if ($bot.open_positions.Count -gt 0) { ^
       Write-Host '  --- Open positions ---' -ForegroundColor Yellow; ^
       $bot.open_positions | ForEach-Object { ^
         $dir = if ($_.metadata.direction) { $_.metadata.direction } else { 'long' }; ^
         Write-Host ('    ' + $dir.ToUpper() + ' ' + $_.symbol + ' entry $' + $_.entry_price + ' -> $' + $_.current_price + '  unrealized $' + $_.unrealized_pnl); ^
       } ^
     } ^
   }"

echo.
echo ================================================================
echo   Pour rafraichir : retape    .\STATUS.bat
echo   Pour voir les logs live  :  Get-Content data\sentiment_ls_v3_lo_log.json -Wait -Tail 20
echo ================================================================
echo.
pause
