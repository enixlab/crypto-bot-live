# =============================================================
# ENIX CRYPTO BOT — Installation automatique sur VPS Windows
# =============================================================
# À exécuter sur ton VPS Contabo Windows en PowerShell (admin)
# Une seule commande, tout s'installe.
# =============================================================

$ErrorActionPreference = "Continue"
Set-ExecutionPolicy Bypass -Scope Process -Force

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ENIX CRYPTO BOT — INSTALLATION AUTO SUR VPS WINDOWS" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# ========== 1. Verifier admin ==========
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERREUR: Lance ce script en ADMINISTRATEUR (clic droit PowerShell -> Executer en admin)" -ForegroundColor Red
    pause
    exit 1
}

# ========== 2. Dossier d'installation ==========
$INSTALL_DIR = "C:\enix-bot"
Write-Host "[1/8] Creation du dossier $INSTALL_DIR" -ForegroundColor Cyan
New-Item -Path $INSTALL_DIR -ItemType Directory -Force | Out-Null
Set-Location $INSTALL_DIR

# ========== 3. Installer Python ==========
Write-Host "[2/8] Verification Python..." -ForegroundColor Cyan
$pythonOk = $false
try {
    $v = python --version 2>&1
    if ($v -match "Python 3") { $pythonOk = $true; Write-Host "  Python deja installe: $v" -ForegroundColor Green }
} catch {}

if (-not $pythonOk) {
    Write-Host "  Installation de Python 3.12..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    $pyInstaller = "$env:TEMP\python_installer.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -UseBasicParsing
    Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
    Remove-Item $pyInstaller
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Host "  Python installe." -ForegroundColor Green
}

# ========== 4. Installer Git ==========
Write-Host "[3/8] Verification Git..." -ForegroundColor Cyan
$gitOk = $false
try {
    $v = git --version 2>&1
    if ($v -match "git version") { $gitOk = $true; Write-Host "  Git deja installe: $v" -ForegroundColor Green }
} catch {}

if (-not $gitOk) {
    Write-Host "  Installation de Git..." -ForegroundColor Yellow
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.45.1.windows.1/Git-2.45.1-64-bit.exe"
    $gitInstaller = "$env:TEMP\git_installer.exe"
    Invoke-WebRequest -Uri $gitUrl -OutFile $gitInstaller -UseBasicParsing
    Start-Process -FilePath $gitInstaller -ArgumentList "/VERYSILENT /NORESTART" -Wait
    Remove-Item $gitInstaller
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Host "  Git installe." -ForegroundColor Green
}

# ========== 5. Cloner le repo ==========
Write-Host "[4/8] Clone du repo crypto-bot-live..." -ForegroundColor Cyan
if (Test-Path "$INSTALL_DIR\crypto-bot-live") {
    Set-Location "$INSTALL_DIR\crypto-bot-live"
    git pull 2>&1 | Out-Host
} else {
    git clone https://github.com/enixlab/crypto-bot-live.git 2>&1 | Out-Host
    Set-Location "$INSTALL_DIR\crypto-bot-live"
}
Write-Host "  Repo a jour." -ForegroundColor Green

# ========== 6. Installer les dependances Python ==========
Write-Host "[5/8] Installation des dependances Python..." -ForegroundColor Cyan
python -m pip install --upgrade pip 2>&1 | Out-Null
python -m pip install python-dotenv requests feedparser PyYAML pydantic google-generativeai openai 2>&1 | Out-Null
Write-Host "  Dependances installees." -ForegroundColor Green

# ========== 7. Configurer le .env (cles API) ==========
Write-Host "[6/8] Configuration des cles API" -ForegroundColor Cyan
if (Test-Path ".env") {
    Write-Host "  .env existe deja. Reutilisation." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "  Colle ta cle DeepSeek (commence par sk-...) :" -ForegroundColor Yellow
    $deepseek = Read-Host "  DEEPSEEK_API_KEY"

    @"
DEEPSEEK_API_KEY=$deepseek
SENTIMENT_MODEL=deepseek-chat
INITIAL_CAPITAL=250
LEVERAGE=3
CYCLE_MINUTES=10
"@ | Out-File -Encoding UTF8 .env -Force
    Write-Host "  .env cree." -ForegroundColor Green
}

# ========== 8. Creer tache planifiee (auto-restart, autostart au boot) ==========
Write-Host "[7/8] Creation de la tache Windows (bot tourne 24/7, auto-restart si crash)..." -ForegroundColor Cyan

$taskName = "EnixCryptoBot"
$pythonExe = (Get-Command python).Source
$workDir = "$INSTALL_DIR\crypto-bot-live"

# Supprimer ancienne tache si existe
schtasks /Delete /TN $taskName /F 2>&1 | Out-Null

# Creer batch wrapper qui restart en boucle si crash
@"
@echo off
cd /d "$workDir"
:loop
"$pythonExe" -m bot.main --mode paper
echo Bot crashed or stopped. Restarting in 30s...
timeout /t 30 /nobreak
goto loop
"@ | Out-File -Encoding ASCII "$workDir\run_forever.bat" -Force

# Tache : demarre au boot, en tant que SYSTEM (tourne meme sans login)
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$workDir\run_forever.bat`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "  Tache planifiee creee. Le bot demarrera tout seul a chaque boot." -ForegroundColor Green

# ========== 9. Lancer maintenant ==========
Write-Host "[8/8] Lancement du bot..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  INSTALLATION TERMINEE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Bot installe dans : $workDir" -ForegroundColor White
Write-Host "Dashboard local    : $workDir\dashboard\index.html" -ForegroundColor White
Write-Host "Logs               : Voir Task Scheduler -> EnixCryptoBot" -ForegroundColor White
Write-Host ""
Write-Host "COMMANDES UTILES :" -ForegroundColor Yellow
Write-Host "  Statut bot     : schtasks /Query /TN EnixCryptoBot" -ForegroundColor Gray
Write-Host "  Arreter        : schtasks /End /TN EnixCryptoBot" -ForegroundColor Gray
Write-Host "  Redemarrer     : schtasks /Run /TN EnixCryptoBot" -ForegroundColor Gray
Write-Host "  Voir logs live : Get-Content $workDir\bot.log -Wait -Tail 50" -ForegroundColor Gray
Write-Host ""
Write-Host "Le bot tourne maintenant 24/7. Tu peux fermer le RDP." -ForegroundColor Green
Write-Host ""
