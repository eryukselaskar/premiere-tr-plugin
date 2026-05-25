# TR Altyazi - Windows Install Script
# Run as Administrator: Set-ExecutionPolicy Bypass -Scope Process
# then: .\install.ps1

$ErrorActionPreference = "Stop"
$ExtDir = "$env:APPDATA\Adobe\CEP\extensions\tr-subtitle"

Write-Host ""
Write-Host "=== TR Altyazi - Premiere Pro Plugin Installer ===" -ForegroundColor Cyan
Write-Host ""

# 1. Copy extension files
Write-Host "[1/3] Copying extension to CEP folder..." -ForegroundColor Yellow
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path $ExtDir) {
    Remove-Item $ExtDir -Recurse -Force
}
Copy-Item -Path $scriptDir -Destination $ExtDir -Recurse
Write-Host "      Copied to: $ExtDir" -ForegroundColor Green

# 2. Enable unsigned extensions (all CSXS versions)
Write-Host "[2/3] Enabling debug mode for unsigned extensions..." -ForegroundColor Yellow
$csxsVersions = @("11", "12", "13")
foreach ($v in $csxsVersions) {
    $key = "HKCU:\Software\Adobe\CSXS.$v"
    if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
    Set-ItemProperty -Path $key -Name "PlayerDebugMode" -Value 1 -Type DWord
}
Write-Host "      Registry keys set for CSXS 11/12/13." -ForegroundColor Green

# 3. Python dependencies
Write-Host "[3/3] Installing Python dependencies..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "      Python not found. Install from https://python.org" -ForegroundColor Red
} else {
    Push-Location "$ExtDir\whisper-server"
    python -m pip install -r ..\requirements.txt --quiet
    Pop-Location
    Write-Host "      Python packages installed." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Installation complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start Whisper server:  cd whisper-server && python whisper_server.py"
Write-Host "  2. Open Premiere Pro"
Write-Host "  3. Window -> Extensions -> TR Altyazi & Transcript"
Write-Host ""
