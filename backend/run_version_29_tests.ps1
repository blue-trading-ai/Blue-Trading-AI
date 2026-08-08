# ============================================================
# Blue-Trading-AI
# Version 29 Full Test Runner
# File: run_version_29_tests.ps1
#
# Place this file in the backend root beside main.py.
#
# Run:
#   .\run_version_29_tests.ps1
#
# It will:
# 1. Validate required Version 29 files
# 2. Run verify_version_29.py
# 3. Start FastAPI temporarily
# 4. Wait for the API to become ready
# 5. Run test_version_29_api.py
# 6. Stop the temporary API process
# ============================================================

$ErrorActionPreference = "Stop"

$HostAddress = "127.0.0.1"
$Port = 8000
$BaseUrl = "http://$HostAddress`:$Port"
$ServerProcess = $null

function Write-Step {
    param(
        [string]$Message
    )

    Write-Host ""
    Write-Host ">> $Message" -ForegroundColor Cyan
}

function Stop-TemporaryServer {
    if ($null -ne $ServerProcess) {
        try {
            if (-not $ServerProcess.HasExited) {
                Write-Host ""
                Write-Host "Stopping temporary FastAPI server..." -ForegroundColor Yellow
                Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
                Wait-Process -Id $ServerProcess.Id -ErrorAction SilentlyContinue
                Write-Host "[OK] Temporary server stopped." -ForegroundColor Green
            }
        }
        catch {
            Write-Host "[WARNING] Could not stop temporary server cleanly." -ForegroundColor Yellow
        }
    }
}

try {
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host " BLUE-TRADING-AI VERSION 29 FULL TEST RUNNER" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host ""

    # --------------------------------------------------------
    # Confirm backend root
    # --------------------------------------------------------

    if (-not (Test-Path ".\main.py")) {
        Write-Host "[ERROR] main.py was not found." -ForegroundColor Red
        Write-Host "Place this script inside the backend root folder." -ForegroundColor Yellow
        exit 1
    }

    if (-not (Test-Path ".\app")) {
        Write-Host "[ERROR] app folder was not found." -ForegroundColor Red
        exit 1
    }

    # --------------------------------------------------------
    # Select Python
    # --------------------------------------------------------

    $PythonCommand = $null

    if (Test-Path ".\venv\Scripts\python.exe") {
        $PythonCommand = (Resolve-Path ".\venv\Scripts\python.exe").Path
        Write-Host "[OK] Virtual environment Python selected." -ForegroundColor Green
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonCommand = "python"
        Write-Host "[WARNING] venv not found. Using system Python." -ForegroundColor Yellow
    }
    else {
        Write-Host "[ERROR] Python was not found." -ForegroundColor Red
        exit 1
    }

    # --------------------------------------------------------
    # Required files
    # --------------------------------------------------------

    Write-Step "Checking Version 29 files"

    $RequiredFiles = @(
        ".\main.py",
        ".\verify_version_29.py",
        ".\test_version_29_api.py",
        ".\app\services\__init__.py",
        ".\app\services\learning_analytics_service.py",
        ".\app\api\learning_analytics.py"
    )

    $MissingFiles = @()

    foreach ($File in $RequiredFiles) {
        if (-not (Test-Path $File)) {
            $MissingFiles += $File
        }
    }

    if ($MissingFiles.Count -gt 0) {
        Write-Host "[ERROR] Missing required files:" -ForegroundColor Red

        foreach ($File in $MissingFiles) {
            Write-Host "  - $File" -ForegroundColor Red
        }

        exit 1
    }

    Write-Host "[OK] All required Version 29 files found." -ForegroundColor Green

    # --------------------------------------------------------
    # Static verification
    # --------------------------------------------------------

    Write-Step "Running Version 29 verification"

    & $PythonCommand ".\verify_version_29.py"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Version 29 verification failed." -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "[OK] Version 29 verification passed." -ForegroundColor Green

    # --------------------------------------------------------
    # Check whether port is already occupied
    # --------------------------------------------------------

    Write-Step "Checking API port $Port"

    $ExistingConnection = Get-NetTCPConnection `
        -LocalPort $Port `
        -State Listen `
        -ErrorAction SilentlyContinue

    if ($ExistingConnection) {
        Write-Host "[ERROR] Port $Port is already in use." -ForegroundColor Red
        Write-Host "Stop the existing API server, then run this script again." -ForegroundColor Yellow
        exit 1
    }

    Write-Host "[OK] Port $Port is available." -ForegroundColor Green

    # --------------------------------------------------------
    # Start temporary FastAPI server
    # --------------------------------------------------------

    Write-Step "Starting temporary FastAPI server"

    $ServerArguments = @(
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        $HostAddress,
        "--port",
        "$Port"
    )

    $ServerProcess = Start-Process `
        -FilePath $PythonCommand `
        -ArgumentList $ServerArguments `
        -WorkingDirectory (Get-Location).Path `
        -PassThru `
        -WindowStyle Hidden

    Write-Host "[OK] Temporary server process started." -ForegroundColor Green
    Write-Host "Process ID: $($ServerProcess.Id)" -ForegroundColor DarkGray

    # --------------------------------------------------------
    # Wait for API readiness
    # --------------------------------------------------------

    Write-Step "Waiting for API readiness"

    $ApiReady = $false
    $MaximumAttempts = 30

    for ($Attempt = 1; $Attempt -le $MaximumAttempts; $Attempt++) {
        if ($ServerProcess.HasExited) {
            Write-Host "[ERROR] FastAPI server stopped unexpectedly." -ForegroundColor Red
            exit 1
        }

        try {
            $Response = Invoke-WebRequest `
                -Uri "$BaseUrl/" `
                -Method Get `
                -TimeoutSec 2 `
                -UseBasicParsing

            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 300) {
                $ApiReady = $true
                break
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }

        Write-Host "Waiting... attempt $Attempt/$MaximumAttempts" -ForegroundColor DarkGray
    }

    if (-not $ApiReady) {
        Write-Host "[ERROR] API did not become ready." -ForegroundColor Red
        exit 1
    }

    Write-Host "[OK] API is ready at $BaseUrl" -ForegroundColor Green

    # --------------------------------------------------------
    # API tests
    # --------------------------------------------------------

    Write-Step "Running Version 29 API tests"

    & $PythonCommand ".\test_version_29_api.py"
    $ApiTestExitCode = $LASTEXITCODE

    if ($ApiTestExitCode -ne 0) {
        Write-Host "[ERROR] Version 29 API tests failed." -ForegroundColor Red
        exit $ApiTestExitCode
    }

    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host " VERSION 29 ALL TESTS PASSED" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Verified:" -ForegroundColor White
    Write-Host "  - Version 29 imports" -ForegroundColor White
    Write-Host "  - Version 29 routes" -ForegroundColor White
    Write-Host "  - Learning analytics summary" -ForegroundColor White
    Write-Host "  - Asian, European and US session analytics" -ForegroundColor White
    Write-Host "  - Confidence calibration" -ForegroundColor White
    Write-Host "  - Risk:Reward analytics" -ForegroundColor White
    Write-Host "  - Learning health score" -ForegroundColor White
    Write-Host "  - Version 28 persistence compatibility" -ForegroundColor White
    Write-Host "  - Analysis-only safety" -ForegroundColor White

    exit 0
}
finally {
    Stop-TemporaryServer
}