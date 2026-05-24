# ============================================================
# deploy_fleet_5.ps1 — étend la flotte ENIX crypto à 5 bots
# À lancer sur le VPS Contabo en PowerShell admin :
#   cd C:\enix-bot\crypto-bot-live
#   git fetch origin; git reset --hard origin/main
#   powershell -ExecutionPolicy Bypass -File .\deploy_fleet_5.ps1
# ============================================================
$ErrorActionPreference = "Continue"
$root = "C:\enix-bot\crypto-bot-live"
$data = Join-Path $root "data"
Set-Location $root

Write-Host "`n== 1. Stop + DISABLE l'orchestrateur legacy EnixCryptoBot ==" -ForegroundColor Cyan
Write-Host "   (il écrit sentiment_ls_v3 / sentiment_ls_v3_tp en format incompatible → collision)"
Stop-ScheduledTask    -TaskName "EnixCryptoBot" -ErrorAction SilentlyContinue
Disable-ScheduledTask -TaskName "EnixCryptoBot" -ErrorAction SilentlyContinue | Out-Null
Start-Sleep -Seconds 2

Write-Host "`n== 2. Archive les vieux state qui collisionnent (départ propre à 200€) ==" -ForegroundColor Cyan
$bk = Join-Path $data ("_legacy_backup_" + (Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $bk -Force | Out-Null
@(
  "sentiment_ls_v3_state.json",    "sentiment_ls_v3_equity.json",    "heartbeat_sentiment_ls_v3.json",
  "sentiment_ls_v3_tp_state.json", "sentiment_ls_v3_tp_equity.json", "heartbeat_sentiment_ls_v3_tp.json"
) | ForEach-Object {
  $p = Join-Path $data $_
  if (Test-Path $p) { Move-Item $p $bk\ -Force; Write-Host "   moved $_" }
}
Write-Host "   backup -> $bk"

Write-Host "`n== 3. Crée + démarre les 2 nouvelles tâches dédiées ==" -ForegroundColor Cyan
$t = New-ScheduledTaskTrigger   -AtStartup
$p = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$s = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

$a1 = New-ScheduledTaskAction -Execute "python" -Argument "bot\zaid_fleet\sentiment_ls_v3.py"    -WorkingDirectory $root
Register-ScheduledTask -TaskName "EnixCryptoBotLS"   -Action $a1 -Trigger $t -Principal $p -Settings $s -Force | Out-Null

$a2 = New-ScheduledTaskAction -Execute "python" -Argument "bot\zaid_fleet\sentiment_ls_v3_tp.py" -WorkingDirectory $root
Register-ScheduledTask -TaskName "EnixCryptoBotLSTP" -Action $a2 -Trigger $t -Principal $p -Settings $s -Force | Out-Null

schtasks /Run /TN EnixCryptoBotLS
schtasks /Run /TN EnixCryptoBotLSTP

Write-Host "`n== 4. État des tâches de la flotte ==" -ForegroundColor Cyan
Get-ScheduledTask -TaskName "EnixCryptoBot*" |
  Select-Object TaskName, State | Format-Table -AutoSize

Write-Host "`n✅ Terminé. Attends ~3-4 min, puis vérifie les heartbeats (doivent être < 300s) :" -ForegroundColor Green
Write-Host "   Get-ChildItem $data\heartbeat_*.json | Select Name, LastWriteTime"
Write-Host "   → heartbeat_sentiment_ls_v3.json et heartbeat_sentiment_ls_v3_tp.json doivent apparaître."
