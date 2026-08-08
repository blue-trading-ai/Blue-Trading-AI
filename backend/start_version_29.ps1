
# ============================================================
# Blue-Trading-AI
# Version 29 Startup Script
# File: start_version_29.ps1
#
# Place this file in the backend root beside main.py.
# Run:
#   .\start_version_29.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " BLUE-TRADING-AI VERSION 29 STARTUP" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Confirm that the script is running from the backend folder.
if (-not (Test-Path ".\main.py")) {
    Write-Host "[ERROR] main.py was not found." -ForegroundColor Red
    Write-Host "Place start_version_29.ps1 inside the backend folder." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path ".\app")) {
    Write-Host "[ERROR] app folder was not found." -ForegroundColor Red
    Write-Host "Run this script from the backend root folder." -ForegroundColor Yellow
    exit 1
}

# Select the Python executable.
$PythonCommand = $null

if (Test-Path ".\venv\Scripts\python.exe") {
    $PythonCommand = ".\venv\Scripts\python.exe"
    Write-Host "[OK] Virtual environment detected." -ForegroundColor Green
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
    Write-Host "[WARNING] venv was not found. Using system Python." -ForegroundColor Yellow
}
else {
    Write-Host "[ERROR] Python was not found." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Verify the expected Version 29 files.
$RequiredFiles = @(
    ".\app\services\learning_analytics_service.py",
    ".\app\api\learning_analytics.py",
    ".\app\services\__init__.py",
    ".\verify_version_29.py"
)

$MissingFiles = @()

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        $MissingFiles += $File
    }
}

if ($MissingFiles.Count -gt 0) {
    Write-Host "[ERROR] Missing Version 29 files:" -ForegroundColor Red

    foreach ($File in $MissingFiles) {
        Write-Host "  - $File" -ForegroundColor Red
    }

    exit 1
}

Write-Host "[OK] Required Version 29 files found." -ForegroundColor Green
Write-Host ""

# Run Version 29 verification before starting the API.
Write-Host "Running Version 29 verification..." -ForegroundColor Cyan
& $PythonCommand ".\verify_version_29.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Version 29 verification failed." -ForegroundColor Red
    Write-Host "Fix the FAIL result before starting the API." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[OK] Version 29 verification passed." -ForegroundColor Green
Write-Host ""
Write-Host "Starting FastAPI server..." -ForegroundColor Cyan
Write-Host "API:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press CTRL+C to stop the server." -ForegroundColor Yellow
Write-Host ""

# Start the FastAPI application.
& $PythonCommand -m uvicorn main:app --reload --host 127.0.0.1 --port 8000