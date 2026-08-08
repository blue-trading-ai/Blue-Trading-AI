$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=============================================="
Write-Host " BLUE-TRADING-AI VERSION 28 STARTUP"
Write-Host "=============================================="
Write-Host ""

if (-not (Test-Path ".\main.py")) {
    Write-Host "ERROR: main.py was not found." -ForegroundColor Red
    Write-Host "Run this script from the backend folder."
    exit 1
}

if (-not (Test-Path ".\verify_version_28.py")) {
    Write-Host "ERROR: verify_version_28.py was not found." -ForegroundColor Red
    exit 1
}

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "[1/5] Activating virtual environment..."
    & ".\venv\Scripts\Activate.ps1"
}
elseif (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "[1/5] Activating virtual environment..."
    & ".\.venv\Scripts\Activate.ps1"
}
else {
    Write-Host "[1/5] No local virtual environment found."
    Write-Host "Using the current Python interpreter."
}

Write-Host ""
Write-Host "[2/5] Checking Python..."
python --version

if ($LASTEXITCODE -ne 0) {
    Write-Host "Python is not available." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[3/5] Running Version 27 database migration check..."

if (Test-Path ".\migrate_trade_history_v27.py") {
    python ".\migrate_trade_history_v27.py"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Database migration failed." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}
else {
    Write-Host "migrate_trade_history_v27.py not found."
    Write-Host "Skipping migration because it may already be complete."
}

Write-Host ""
Write-Host "[4/5] Verifying Version 28..."
python ".\verify_version_28.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Version 28 verification failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[5/5] Starting Blue-Trading-AI Version 28..."
Write-Host "API:  http://127.0.0.1:8000"
Write-Host "Docs: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Persistent Learning Intelligence will rebuild"
Write-Host "automatically from completed database trades."
Write-Host ""
Write-Host "Press CTRL+C to stop the server."
Write-Host ""

python -m uvicorn main:app --reload