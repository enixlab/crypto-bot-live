$workDir = 'C:\enix-bot\crypto-bot-live'

$bots = @(
    @{ Name = 'EnixCryptoBotLO';        Script = 'bot\zaid_fleet\sentiment_ls_v3_lo.py' },
    @{ Name = 'EnixCryptoBotConfRev';   Script = 'bot\zaid_fleet\confluence_reverse.py' },
    @{ Name = 'EnixCryptoBotUltRev';    Script = 'bot\zaid_fleet\ultimate_v2_reverse.py' }
)

foreach ($b in $bots) {
    $action = New-ScheduledTaskAction -Execute 'python' -Argument $b.Script -WorkingDirectory $workDir
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $b.Name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    schtasks /End /TN $b.Name 2>$null | Out-Null
    Start-Sleep -Seconds 1
    schtasks /Run /TN $b.Name | Out-Null
    Write-Host "  OK $($b.Name)" -ForegroundColor Green
}
