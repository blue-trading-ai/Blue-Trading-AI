# ============================================================
# Blue-Trading-AI
# Version 29 Backup Script
# File: backup_version_29.ps1
#
# Place this file in the backend root beside main.py.
#
# Run:
#   .\backup_version_29.ps1
#
# The script creates a timestamped ZIP backup while excluding:
# - venv
# - __pycache__
# - .pytest_cache
# - .git
# - temporary Python files
# - existing ZIP backups
# ============================================================

$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Message)

    Write-Host ""
    Write-Host ">> $Message" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " BLUE-TRADING-AI VERSION 29 BACKUP" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Confirm this is the backend root.
if (-not (Test-Path ".\main.py")) {
    Write-Host "[ERROR] main.py was not found." -ForegroundColor Red
    Write-Host "Place this script inside the backend root folder." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path ".\app")) {
    Write-Host "[ERROR] app folder was not found." -ForegroundColor Red
    exit 1
}

Write-Section "Checking Version 29 files"

$RequiredFiles = @(
    ".\main.py",
    ".\verify_version_29.py",
    ".\test_version_29_api.py",
    ".\start_version_29.ps1",
    ".\run_version_29_tests.ps1",
    ".\app\services\learning_analytics_service.py",
    ".\app\api\learning_analytics.py",
    ".\app\services\__init__.py"
)

$MissingFiles = @()

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        $MissingFiles += $File
    }
}

if ($MissingFiles.Count -gt 0) {
    Write-Host "[WARNING] Some Version 29 files are missing:" -ForegroundColor Yellow

    foreach ($File in $MissingFiles) {
        Write-Host "  - $File" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Backup will continue with the files currently available." -ForegroundColor Yellow
}
else {
    Write-Host "[OK] All expected Version 29 files found." -ForegroundColor Green
}

# Create backup location outside the backend folder.
$BackendPath = (Get-Location).Path
$ProjectPath = Split-Path $BackendPath -Parent
$BackupRoot = Join-Path $ProjectPath "backups"

if (-not (Test-Path $BackupRoot)) {
    New-Item `
        -ItemType Directory `
        -Path $BackupRoot `
        -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupName = "Blue-Trading-AI_Backend_V29_$Timestamp"
$TemporaryFolder = Join-Path $env:TEMP $BackupName
$ZipPath = Join-Path $BackupRoot "$BackupName.zip"

Write-Section "Preparing clean backup copy"

if (Test-Path $TemporaryFolder) {
    Remove-Item `
        -Path $TemporaryFolder `
        -Recurse `
        -Force
}

New-Item `
    -ItemType Directory `
    -Path $TemporaryFolder `
    -Force | Out-Null

$ExcludedDirectories = @(
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "backups"
)

$ExcludedExtensions = @(
    ".pyc",
    ".pyo",
    ".tmp",
    ".log",
    ".zip"
)

$CopiedFiles = 0
$SkippedFiles = 0

Get-ChildItem `
    -Path $BackendPath `
    -Recurse `
    -File | ForEach-Object {

    $SourceFile = $_
    $RelativePath = $SourceFile.FullName.Substring(
        $BackendPath.Length
    ).TrimStart("\", "/")

    $RelativeParts = $RelativePath -split "[\\/]"
    $ShouldSkip = $false

    foreach ($Part in $RelativeParts) {
        if ($ExcludedDirectories -contains $Part) {
            $ShouldSkip = $true
            break
        }
    }

    if ($ExcludedExtensions -contains $SourceFile.Extension.ToLower()) {
        $ShouldSkip = $true
    }

    if ($ShouldSkip) {
        $SkippedFiles++
        return
    }

    $DestinationFile = Join-Path $TemporaryFolder $RelativePath
    $DestinationDirectory = Split-Path $DestinationFile -Parent

    if (-not (Test-Path $DestinationDirectory)) {
        New-Item `
            -ItemType Directory `
            -Path $DestinationDirectory `
            -Force | Out-Null
    }

    Copy-Item `
        -Path $SourceFile.FullName `
        -Destination $DestinationFile `
        -Force

    $CopiedFiles++
}

Write-Host "[OK] Copied files: $CopiedFiles" -ForegroundColor Green
Write-Host "[INFO] Skipped files: $SkippedFiles" -ForegroundColor DarkGray

# Add backup information.
$ManifestPath = Join-Path $TemporaryFolder "VERSION_29_BACKUP_INFO.txt"

$Manifest = @"
Blue-Trading-AI Backend Backup
Version: 29
Created: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Source: $BackendPath
Copied files: $CopiedFiles
Skipped files: $SkippedFiles

Version 29 safeguards:
- Minimum completed trades: 20
- Maximum confidence adjustment: +/-4
- Session analytics: Asian, European and US
- Timeframe learning: Disabled
- Strategy optimization: Disabled
- Strategy ranking: Disabled
- Broker connection: Disabled
- Automatic trade execution: Disabled
- Analysis-only mode: Enabled
"@

Set-Content `
    -Path $ManifestPath `
    -Value $Manifest `
    -Encoding UTF8

Write-Section "Creating ZIP backup"

if (Test-Path $ZipPath) {
    Remove-Item `
        -Path $ZipPath `
        -Force
}

Compress-Archive `
    -Path (Join-Path $TemporaryFolder "*") `
    -DestinationPath $ZipPath `
    -CompressionLevel Optimal `
    -Force

if (-not (Test-Path $ZipPath)) {
    Write-Host "[ERROR] Backup ZIP was not created." -ForegroundColor Red
    exit 1
}

$ZipFile = Get-Item $ZipPath
$ZipSizeMB = [Math]::Round(
    $ZipFile.Length / 1MB,
    2
)

# Remove temporary working folder.
Remove-Item `
    -Path $TemporaryFolder `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " VERSION 29 BACKUP COMPLETED" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backup file:" -ForegroundColor White
Write-Host $ZipPath -ForegroundColor Yellow
Write-Host ""
Write-Host "Backup size: $ZipSizeMB MB" -ForegroundColor White
Write-Host "Files copied: $CopiedFiles" -ForegroundColor White
Write-Host ""
Write-Host "Keep this ZIP before starting Version 30." -ForegroundColor Cyan