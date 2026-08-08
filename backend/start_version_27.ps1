$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=============================================="
Write-Host " BLUE-TRADING-AI VERSION 27 STARTUP"
Write-Host "=============================================="
Write-Host ""

# Confirm this script is running from the backend folder.
if (-not (Test-Path ".\main.py")) {
    Write-Host "ERROR: main.py was not found." -ForegroundColor Red
    Write-Host "Open PowerShell inside the backend folder and run this script again."
    exit 1
}

if (-not (Test-Path ".\migrate_trade_history_v27.py")) {
    Write-Host "ERROR: migrate_trade_history_v27.py was not found." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".\verify_version_27.py")) {
    Write-Host "ERROR: verify_version_27.py was not found." -ForegroundColor Red
    exit 1
}

# Activate the virtual environment when present.
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "[1/5] Activating virtual environment..."
    & ".\venv\Scripts\Activate.ps1"
}
elseif (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "[1/5] Activating virtual environment..."
    & ".\.venv\Scripts\Activate.ps1"
}
else {
    Write-Host "[1/5] No local virtual environment activation script found."
    Write-Host "Using the currently available Python interpreter."
}

Write-Host ""
Write-Host "[2/5] Checking Python..."
python --version

Write-Host ""
Write-Host "[3/5] Running Version 27 database migration..."
python ".\migrate_trade_history_v27.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Migration failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[4/5] Verifying Version 27..."
python ".\verify_version_27.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Version 27 verification failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[5/5] Starting Blue-Trading-AI..."
Write-Host "API: http://127.0.0.1:8000"
Write-Host "Docs: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Press CTRL+C to stop the server."
Write-Host ""

python -m uvicorn main:app --reload