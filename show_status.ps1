$files = @(
    'data\sentiment_ls_v3_lo_state.json',
    'data\confluence_reverse_state.json',
    'data\ultimate_v2_reverse_state.json'
)

$total_eq = 0
$total_init = 0

foreach ($f in $files) {
    if (-not (Test-Path $f)) {
        Write-Host "  $f : MANQUANT (bot pas encore demarre)" -ForegroundColor Yellow
        continue
    }
    $bot = Get-Content $f -Raw | ConvertFrom-Json
    $eq = [math]::Round($bot.equity, 2)
    $init = [math]::Round($bot.initial_capital, 2)
    $pnl = [math]::Round($eq - $init, 2)
    $pct = if ($init -gt 0) { [math]::Round(($pnl / $init) * 100, 2) } else { 0 }
    $color = if ($pnl -ge 0) { 'Green' } else { 'Red' }

    $total_eq += $eq
    $total_init += $init

    Write-Host ''
    Write-Host '=== ' -NoNewline
    Write-Host $bot.bot_id -ForegroundColor Cyan
    Write-Host ('  Equity      : $' + $eq + '  (init $' + $init + ')')
    Write-Host ('  PnL         : $' + $pnl + ' (' + $pct + '%)') -ForegroundColor $color
    Write-Host ('  Positions   : ' + $bot.open_positions.Count + ' open / ' + $bot.closed_trades.Count + ' closed')
    Write-Host ('  Cycles      : ' + $bot.cycle_count)
    Write-Host ('  Last cycle  : ' + $bot.last_cycle)
    Write-Host ('  Regime      : ' + $bot.custom.macro_regime + ' | F&G=' + $bot.custom.fear_greed + ' | Stress=' + $bot.custom.stress_mode)

    if ($bot.open_positions.Count -gt 0) {
        Write-Host '  --- Open positions ---' -ForegroundColor Yellow
        foreach ($p in $bot.open_positions) {
            $dir = if ($p.metadata.direction) { $p.metadata.direction.ToUpper() } else { 'LONG' }
            Write-Host ('    ' + $dir + ' ' + $p.symbol + ' entry $' + $p.entry_price + ' -> $' + $p.current_price + '  unrealized $' + $p.unrealized_pnl)
        }
    }
}

Write-Host ''
Write-Host '================================================================'
Write-Host ('  TOTAL: equity $' + $total_eq + '  (init $' + $total_init + ')   PnL $' + ($total_eq - $total_init)) -ForegroundColor Cyan
Write-Host '================================================================'
