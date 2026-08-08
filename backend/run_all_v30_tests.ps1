param(
    [string]$PythonCommand = "python",
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [switch]$SkipApiTests
)

$ErrorActionPreference = "Continue"

function Write-Section {
    param([string]$Title)

    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host $Title
    Write-Host ("=" * 78)
}

function Invoke-PythonTest {
    param(
        [string]$Name,
        [string]$FileName,
        [bool]$Required = $true
    )

    Write-Section $Name

    if (-not (Test-Path $FileName)) {
        if ($Required) {
            Write-Host "[FAIL] Missing required file: $FileName"
            return $false
        }

        Write-Host "[SKIP] Optional file not found: $FileName"
        return $true
    }

    & $PythonCommand $FileName
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "[PASS] $Name"
        return $true
    }

    Write-Host "[FAIL] $Name returned exit code $exitCode"
    return $false
}

function Test-ApiReady {
    param([string]$Url)

    try {
        $response = Invoke-RestMethod `
            -Uri "$Url/health" `
            -Method Get `
            -TimeoutSec 8

        Write-Host "[PASS] FastAPI is reachable at $Url"
        return $true
    }
    catch {
        try {
            $response = Invoke-RestMethod `
                -Uri "$Url/" `
                -Method Get `
                -TimeoutSec 8

            Write-Host "[PASS] FastAPI is reachable at $Url"
            return $true
        }
        catch {
            Write-Host "[FAIL] FastAPI is not reachable at $Url"
            Write-Host "Start it in another terminal with:"
            Write-Host "python -m uvicorn main:app --reload"
            return $false
        }
    }
}

Write-Section "BLUE-TRADING-AI VERSION 30 FULL VERIFICATION"

Write-Host "Project directory: $(Get-Location)"
Write-Host "Python command: $PythonCommand"
Write-Host "API URL: $ApiUrl"
Write-Host "Analysis only: enabled"
Write-Host "Broker connection: disabled"
Write-Host "Trade execution: disabled"

$results = New-Object System.Collections.Generic.List[bool]

$results.Add(
    (Invoke-PythonTest `
        -Name "Database Verification" `
        -FileName "verify_database_v30.py")
)

$results.Add(
    (Invoke-PythonTest `
        -Name "Master Pipeline Verification" `
        -FileName "verify_master_pipeline_v30.py")
)

if (-not $SkipApiTests) {
    Write-Section "FASTAPI AVAILABILITY"

    $apiReady = Test-ApiReady -Url $ApiUrl
    $results.Add($apiReady)

    if ($apiReady) {
        $results.Add(
            (Invoke-PythonTest `
                -Name "Master Pipeline API Test" `
                -FileName "test_master_signal_pipeline_v30_api.py")
        )

        $results.Add(
            (Invoke-PythonTest `
                -Name "Trading API Test" `
                -FileName "test_trading_v30_api.py")
        )
    }
}
else {
    Write-Section "API TESTS"
    Write-Host "[SKIP] API tests skipped by -SkipApiTests"
}

Write-Section "VERSION 30 SAFETY FILE CHECK"

$requiredFiles = @(
    "main.py",
    "app\api\trading.py",
    "app\api\history.py",
    "app\api\master_signal_pipeline.py",
    "app\api\confidence_guardrail.py",
    "app\models\trade_history.py",
    "app\schemas\trade_history.py",
    "app\services\trade_history_service.py",
    "app\services\master_signal_pipeline_service.py",
    "app\services\confidence_guardrail_service.py",
    "app\services\confidence_guardrail_integration.py",
    "app\database\connection.py"
)

$fileCheckPassed = $true

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "[PASS] $file"
    }
    else {
        Write-Host "[FAIL] Missing $file"
        $fileCheckPassed = $false
    }
}

$results.Add($fileCheckPassed)

Write-Section "PYTHON IMPORT CHECK"

$importCode = @'
import importlib

modules = [
    "main",
    "app.api.trading",
    "app.api.history",
    "app.api.master_signal_pipeline",
    "app.api.confidence_guardrail",
    "app.models.trade_history",
    "app.schemas.trade_history",
    "app.services.trade_history_service",
    "app.services.master_signal_pipeline_service",
    "app.services.confidence_guardrail_service",
    "app.services.confidence_guardrail_integration",
    "app.database.connection",
]

for module_name in modules:
    importlib.import_module(module_name)
    print(f"[PASS] Imported {module_name}")
'@

$tempImportFile = Join-Path `
    (Get-Location) `
    "_blue_trading_ai_v30_import_check.py"

Set-Content `
    -Path $tempImportFile `
    -Value $importCode `
    -Encoding UTF8

& $PythonCommand $tempImportFile
$importExitCode = $LASTEXITCODE

Remove-Item `
    -Path $tempImportFile `
    -Force `
    -ErrorAction SilentlyContinue

$importPassed = $importExitCode -eq 0
$results.Add($importPassed)

if ($importPassed) {
    Write-Host "[PASS] Python import check"
}
else {
    Write-Host "[FAIL] Python import check"
}

Write-Section "FINAL RESULT"

$passedCount = (
    $results |
    Where-Object { $_ -eq $true }
).Count

$totalCount = $results.Count
$failedCount = $totalCount - $passedCount

Write-Host "Passed: $passedCount"
Write-Host "Failed: $failedCount"
Write-Host "Total:  $totalCount"

if ($failedCount -eq 0) {
    Write-Host ""
    Write-Host "VERSION 30 BACKEND VERIFICATION PASSED."
    Write-Host "The backend remains analysis-only."
    exit 0
}

Write-Host ""
Write-Host "VERSION 30 BACKEND VERIFICATION FAILED."
Write-Host "Review the FAIL lines above."
exit 1