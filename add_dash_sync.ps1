# ============================================================
# add_dash_sync.ps1 — crée la tâche dédiée de synchro dashboard
# (remplace le push que faisait l'orchestrateur legacy désactivé)
# À lancer sur le VPS :
#   cd C:\enix-bot\crypto-bot-live
#   git fetch origin; git reset --hard origin/main
#   powershell -ExecutionPolicy Bypass -File .\add_dash_sync.ps1
# ============================================================
$ErrorActionPreference = "Continue"
$root = "C:\enix-bot\crypto-bot-live"
Set-Location $root

Write-Host "`n== Crée + démarre la tâche EnixDashSync (push data-feed toutes les 3 min) ==" -ForegroundColor Cyan
$t = New-ScheduledTaskTrigger   -AtStartup
$p = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$s = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$a = New-ScheduledTaskAction -Execute "python" -Argument "bot\core\dash_sync_loop.py" -WorkingDirectory $root
Register-ScheduledTask -TaskName "EnixDashSync" -Action $a -Trigger $t -Principal $p -Settings $s -Force | Out-Null
schtasks /Run /TN EnixDashSync

Start-Sleep -Seconds 3
Write-Host "`n== État de la flotte ==" -ForegroundColor Cyan
Get-ScheduledTask -TaskName "EnixCryptoBot*","EnixDashSync" |
  Select-Object TaskName, State | Format-Table -AutoSize

Write-Host "`n✅ Sync relancée. Le feed GitHub va se rafraîchir d'ici ~3 min." -ForegroundColor Green
Write-Host "   Vérifie : (Get-Content $root\dashboard\dashboard_data.js -TotalCount 3)"
