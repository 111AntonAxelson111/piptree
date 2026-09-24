$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinDir    = "$env:USERPROFILE\.local\bin"
$CmdName   = "piptree"

# 1. Sanity: python present?
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'python' not found on PATH." -ForegroundColor Red
    Write-Host "Install Python from python.org and check 'Add Python to PATH'."
    exit 1
}

# 2. Sanity: piptree.py present next to this script?
if (-not (Test-Path "$ScriptDir\piptree.py")) {
    Write-Host "ERROR: piptree.py not found next to setup.ps1." -ForegroundColor Red
    exit 1
}

# 3. Install
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item "$ScriptDir\piptree.py" "$BinDir\piptree.py" -Force

$launcher = "@echo off`r`npython `"%~dp0piptree.py`" %*"
Set-Content -Path "$BinDir\$CmdName.cmd" -Value $launcher -Encoding ASCII

# 4. PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    Write-Host "Added $BinDir to PATH."
}

Write-Host ""
Write-Host "Installed!" -ForegroundColor Green
Write-Host "Close this terminal, open a NEW one, then run:"
Write-Host "    piptree numpy"