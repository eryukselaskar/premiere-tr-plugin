# TR Altyazi - Windows Install Script
# Run as Administrator: Set-ExecutionPolicy Bypass -Scope Process
# then: .\install.ps1

$ErrorActionPreference = "Stop"
$ExtDir = "$env:APPDATA\Adobe\CEP\extensions\tr-subtitle"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "=== TR Altyazi - Premiere Pro Plugin Installer ===" -ForegroundColor Cyan
Write-Host ""

# 1. Copy extension files
#    venv/.git/__pycache__ kopyalanmaz: venv tasinabilir degildir (kaynak Python'a mutlak
#    yol icerir), bu makinede adim 3'te sifirdan olusturulur.
Write-Host "[1/3] Copying extension to CEP folder..." -ForegroundColor Yellow
if (Test-Path $ExtDir) {
    Remove-Item $ExtDir -Recurse -Force
}
New-Item -ItemType Directory -Path $ExtDir -Force | Out-Null
robocopy $scriptDir $ExtDir /E /XD ".git" "venv" "__pycache__" /NFL /NDL /NJH /NJS /NC /NS | Out-Null
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

# 3. Create a fresh venv on THIS machine and install Python dependencies into it
Write-Host "[3/3] Setting up Python environment (venv)..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "      Python not found. Install from https://python.org" -ForegroundColor Red
} else {
    Push-Location "$ExtDir\whisper-server"
    python -m venv venv
    .\venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    .\venv\Scripts\python.exe -m pip install -r ..\requirements.txt --quiet
    Pop-Location
    Write-Host "      venv created and packages installed." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Installation complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Restart Premiere Pro"
Write-Host "  2. Window -> Extensions -> TR Altyazi & Transcript"
Write-Host "     (Whisper server panel acilince otomatik baslar - ilk acilista large-v3"
Write-Host "      modeli (~3 GB) inecek, biraz surebilir)"
Write-Host ""
