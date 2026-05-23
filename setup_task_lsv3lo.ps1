$action = New-ScheduledTaskAction -Execute 'python' -Argument 'bot\zaid_fleet\sentiment_ls_v3_lo.py' -WorkingDirectory 'C:\enix-bot\crypto-bot-live'
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'EnixCryptoBotLO' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
schtasks /End /TN EnixCryptoBotLO 2>$null | Out-Null
Start-Sleep -Seconds 2
schtasks /Run /TN EnixCryptoBotLO | Out-Null
Write-Host '  OK. Bot lance.' -ForegroundColor Green
