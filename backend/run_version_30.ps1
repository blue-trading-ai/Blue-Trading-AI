
# ============================================================
# Blue-Trading-AI
# Version 30 Startup and Test Script
# File: run_version_30.ps1
#
# Place this file in the backend root beside main.py.
#
# Run:
#   .\run_version_30.ps1
#
# It will:
# 1. Check required Version 30 files
# 2. Run verify_version_30.py
# 3. Start FastAPI
# 4. Test Version 30 guardrail endpoints
# 5. Keep the API server running if tests pass
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " BLUE-TRADING-AI VERSION 30 STARTUP" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Confirm backend root.
if (-not (Test-Path ".\main.py")) {
    Write-Host "[ERROR] main.py was not found." -ForegroundColor Red
    Write-Host "Place this script inside the backend root folder." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path ".\app")) {
    Write-Host "[ERROR] app folder was not found." -ForegroundColor Red
    exit 1
}

# Select Python.
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

# Required files.
$RequiredFiles = @(
    ".\main.py",
    ".\verify_version_30.py",
    ".\app\services\__init__.py",
    ".\app\services\confidence_guardrail_service.py",
    ".\app\api\confidence_guardrail.py",
    ".\app\services\learning_analytics_service.py"
)

$MissingFiles = @()

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        $MissingFiles += $File
    }
}

if ($MissingFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] Missing Version 30 files:" -ForegroundColor Red

    foreach ($File in $MissingFiles) {
        Write-Host "  - $File" -ForegroundColor Red
    }

    exit 1
}

Write-Host "[OK] All required Version 30 files found." -ForegroundColor Green
Write-Host ""

# Run verification first.
Write-Host "Running Version 30 verification..." -ForegroundColor Cyan
& $PythonCommand ".\verify_version_30.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Version 30 verification failed." -ForegroundColor Red
    Write-Host "Review the FAIL message before starting the API." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[OK] Version 30 verification passed." -ForegroundColor Green
Write-Host ""

# Check port.
$Port = 8000
$ExistingConnection = Get-NetTCPConnection `
    -LocalPort $Port `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($ExistingConnection) {
    Write-Host "[ERROR] Port $Port is already in use." -ForegroundColor Red
    Write-Host "Stop the existing server and run again." -ForegroundColor Yellow
    exit 1
}

# Start API as a background process for testing.
Write-Host "Starting temporary FastAPI server..." -ForegroundColor Cyan

$ServerProcess = Start-Process `
    -FilePath $PythonCommand `
    -ArgumentList @(
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "$Port"
    ) `
    -WorkingDirectory (Get-Location).Path `
    -PassThru `
    -WindowStyle Hidden

$BaseUrl = "http://127.0.0.1:$Port"
$ApiReady = $false

for ($Attempt = 1; $Attempt -le 30; $Attempt++) {
    if ($ServerProcess.HasExited) {
        Write-Host "[ERROR] FastAPI stopped unexpectedly." -ForegroundColor Red
        exit 1
    }

    try {
        $Response = Invoke-WebRequest `
            -Uri "$BaseUrl/confidence-guardrail/health" `
            -Method Get `
            -TimeoutSec 2 `
            -UseBasicParsing

        if ($Response.StatusCode -eq 200) {
            $ApiReady = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 1
    }

    Write-Host "Waiting for API... $Attempt/30" -ForegroundColor DarkGray
}

if (-not $ApiReady) {
    Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[ERROR] API did not become ready." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] API is ready." -ForegroundColor Green
Write-Host ""

# Test rules endpoint.
Write-Host "Testing Version 30 rules endpoint..." -ForegroundColor Cyan

$RulesResponse = Invoke-RestMethod `
    -Uri "$BaseUrl/confidence-guardrail/rules" `
    -Method Get `
    -TimeoutSec 10

$Rules = $RulesResponse.data

$RulesPassed = (
    $Rules.minimum_completed_trades -eq 20 -and
    $Rules.maximum_confidence_adjustment -eq 4 -and
    $Rules.minimum_signal_confidence -eq 80 -and
    $Rules.timeframe_performance_enabled -eq $false -and
    $Rules.strategy_optimization_enabled -eq $false -and
    $Rules.strategy_ranking_enabled -eq $false -and
    $Rules.analysis_only -eq $true
)

if (-not $RulesPassed) {
    Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[ERROR] Version 30 rule validation failed." -ForegroundColor Red
    exit 1
}

Write-Host "[PASS] Version 30 rules are correct." -ForegroundColor Green

# Test no-trade below 80.
Write-Host "Testing below-80 confidence protection..." -ForegroundColor Cyan

$BelowThresholdPayload = @{
    base_confidence = 79
    symbol = "XAUUSD"
    market_session = "asian"
    market_condition = "trending"
    direction = "BUY"
} | ConvertTo-Json

$BelowThresholdResponse = Invoke-RestMethod `
    -Uri "$BaseUrl/confidence-guardrail/evaluate" `
    -Method Post `
    -ContentType "application/json" `
    -Body $BelowThresholdPayload `
    -TimeoutSec 10

$BelowThresholdData = $BelowThresholdResponse.data

if (
    $BelowThresholdData.trade_allowed -ne $false -or
    $BelowThresholdData.decision -ne "NO_TRADE"
) {
    Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[ERROR] Below-80 protection failed." -ForegroundColor Red
    exit 1
}

Write-Host "[PASS] Below-80 confidence is blocked." -ForegroundColor Green

# Test approved threshold.
Write-Host "Testing 80-confidence approval..." -ForegroundColor Cyan

$ApprovedPayload = @{
    base_confidence = 80
    symbol = "BTCUSD"
    market_session = "us"
    market_condition = "breakout"
    direction = "SELL"
} | ConvertTo-Json

$ApprovedResponse = Invoke-RestMethod `
    -Uri "$BaseUrl/confidence-guardrail/evaluate" `
    -Method Post `
    -ContentType "application/json" `
    -Body $ApprovedPayload `
    -TimeoutSec 10

$ApprovedData = $ApprovedResponse.data

if (
    $ApprovedData.trade_allowed -ne $true -or
    $ApprovedData.decision -ne "TRADE_SIGNAL"
) {
    Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[ERROR] 80-confidence approval failed." -ForegroundColor Red
    exit 1
}

Write-Host "[PASS] 80-confidence signal is approved." -ForegroundColor Green
Write-Host ""

# Stop the temporary hidden server.
Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
Wait-Process -Id $ServerProcess.Id -ErrorAction SilentlyContinue

Write-Host "==================================================" -ForegroundColor Green
Write-Host " VERSION 30 TESTS PASSED" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Starting normal FastAPI server..." -ForegroundColor Cyan
Write-Host "API:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press CTRL+C to stop the server." -ForegroundColor Yellow
Write-Host ""

& $PythonCommand -m uvicorn main:app --reload --host 127.0.0.1 --port 8000