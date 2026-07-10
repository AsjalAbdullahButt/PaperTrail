# PaperTrail dev launcher.
# Opens the backend (FastAPI/uvicorn) and frontend (Next.js) each in their own
# PowerShell window so they keep running independently of any editor/agent
# session. Close the spawned windows (or Ctrl+C in them) to stop the servers.
#
# Usage:  right-click > "Run with PowerShell", or from a terminal:
#           powershell -ExecutionPolicy Bypass -File .\start-dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Write-Host "Starting PaperTrail dev servers..." -ForegroundColor Cyan

# Backend: activate venv, run uvicorn with autoreload on :8000.
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$backend'; .\venv\Scripts\Activate.ps1; " +
    "uvicorn app.main:app --reload --port 8000"
)

# Frontend: Next.js dev server on :3000.
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$frontend'; npm run dev"
)

Write-Host ""
Write-Host "Backend  -> http://localhost:8000  (health: /api/health)" -ForegroundColor Green
Write-Host "Frontend -> http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "Two new terminal windows opened. Close them to stop the servers." -ForegroundColor Yellow
