$ErrorActionPreference = "Stop"

function Require-Command([string] $name, [string] $installHint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "Missing required command: $name" -ForegroundColor Red
    Write-Host $installHint -ForegroundColor Yellow
    exit 1
  }
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Require-Command "python" "Install Python 3.10+ and ensure it is on PATH."
Require-Command "npm" "Install Node.js (includes npm) and ensure it is on PATH."

Write-Host "Starting VyapaarSetu..." -ForegroundColor Cyan
Write-Host "Root: $root"

# Backend
$backendCmd = "Set-Location '$root'; python -m uvicorn backend.main:app --reload --port 8000 --host 0.0.0.0"
Start-Process powershell -ArgumentList @(
  "-NoLogo", "-NoExit", "-Command", $backendCmd
) | Out-Null
Write-Host "Backend starting on http://localhost:8000" -ForegroundColor Green

# Frontend
$frontendCmd = "Set-Location '$root\frontend'; npm run dev"
Start-Process powershell -ArgumentList @(
  "-NoLogo", "-NoExit", "-Command", $frontendCmd
) | Out-Null
Write-Host "Frontend starting (see its window for the URL)" -ForegroundColor Green

Write-Host ""
Write-Host "If this is your first run:" -ForegroundColor Yellow
Write-Host "  - Backend deps:  python -m pip install -r backend\requirements.txt"
Write-Host "  - Frontend deps: npm install"
Write-Host ""

