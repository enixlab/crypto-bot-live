# ============================================================
#  EnixWatchdog — self-healing de la flotte de bots
#  Verifie toutes les 5 min que chaque tache est Running ;
#  relance automatiquement celles qui sont tombees.
#  Survit aux reboots (-AtStartup + -StartWhenAvailable).
# ============================================================
$ErrorActionPreference = 'Stop'
$workDir = 'C:\enix-bot\crypto-bot-live'
$wdPath  = Join-Path $workDir 'enix_watchdog.ps1'

# --- 1. Ecrit le script watchdog que la tache executera ---
$watchdog = @'
$flotte = @(
  'EnixCryptoBotLO','EnixCryptoBotConfRev','EnixCryptoBotUltRev',
  'EnixCryptoBotLS','EnixCryptoBotLSTP','EnixDashSync'
)
$log = 'C:\enix-bot\crypto-bot-live\data\watchdog.log'
foreach ($t in $flotte) {
    $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if ($null -eq $task) { continue }
    if ($task.State -ne 'Running') {
        schtasks /Run /TN $t | Out-Null
        Add-Content -Path $log -Value ("{0} RESTART {1} (etait {2})" -f (Get-Date).ToString('s'), $t, $task.State)
    }
}
'@
Set-Content -Path $wdPath -Value $watchdog -Encoding UTF8
Write-Host "Watchdog ecrit -> $wdPath" -ForegroundColor Green

# --- 2. Cree / remplace la tache EnixWatchdog ---
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wdPath`"" `
    -WorkingDirectory $workDir
$tBoot = New-ScheduledTaskTrigger -AtStartup
$tRep  = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'EnixWatchdog' -Action $action -Trigger @($tBoot,$tRep) `
    -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Tache EnixWatchdog creee/mise a jour." -ForegroundColor Green

# --- 3. Lance la flotte maintenant (au cas ou) puis le watchdog ---
'EnixCryptoBotLO','EnixCryptoBotConfRev','EnixCryptoBotUltRev','EnixCryptoBotLS','EnixCryptoBotLSTP','EnixDashSync' | ForEach-Object {
    if ((Get-ScheduledTask -TaskName $_ -EA SilentlyContinue).State -ne 'Running') { schtasks /Run /TN $_ | Out-Null }
}
schtasks /Run /TN EnixWatchdog | Out-Null

# --- 4. Verification ---
Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
$rep = ($((Get-ScheduledTask -TaskName 'EnixWatchdog').Triggers) | Where-Object { $_.Repetition.Interval } | Select-Object -First 1).Repetition.Interval
Write-Host ("Repetition watchdog : {0}  (doit etre PT5M)" -f $rep) -ForegroundColor Yellow
Get-ScheduledTask EnixCryptoBot*,EnixDashSync,EnixWatchdog | Format-Table TaskName,State -AutoSize
Write-Host "OK. Le watchdog relancera tout bot tombe, toutes les 5 min, meme apres reboot." -ForegroundColor Green
