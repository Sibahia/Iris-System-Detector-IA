<#
.SYNOPSIS
    Ejecuta tests en Docker replicando el entorno exacto de GitHub Actions CI.
.DESCRIPTION
    Corre pytest dentro de python:3.14-slim (mismo OS y version que ubuntu-latest en CI).
    Si pasa aqui, pasara en CI.
.USAGE
    .\scripts\run_tests_docker.ps1
    .\scripts\run_tests_docker.ps1 -Verbose
#>

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Iris System Detector - Docker Test Runner" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray
Write-Host ""

# Check Docker is available
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "Docker: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 1: Lint with flake8..." -ForegroundColor Yellow
$lintResult = docker run --rm -v "${ProjectRoot}:/app" -w /app python:3.14-slim bash -c `
    "pip install flake8 -q 2>/dev/null && flake8 app.py src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "LINT FAILED" -ForegroundColor Red
    exit 1
}
Write-Host "Lint: PASSED" -ForegroundColor Green

Write-Host ""
Write-Host "Step 2: Installing dependencies..." -ForegroundColor Yellow
docker run --rm -v "${ProjectRoot}:/app" -w /app python:3.14-slim bash -c `
    "pip install -r requirements.txt -r requirements-test.txt -q 2>/dev/null"

Write-Host ""
Write-Host "Step 3: Running pytest..." -ForegroundColor Yellow

$pytestArgs = "pytest tests/ -v --tb=short"
if ($Verbose) {
    $pytestArgs = "pytest tests/ -v --tb=long -s"
}

$testResult = docker run --rm -v "${ProjectRoot}:/app" -w /app -e PYTHONPATH=. python:3.14-slim bash -c $pytestArgs 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "TESTS FAILED" -ForegroundColor Red
    Write-Host $testResult
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " ALL TESTS PASSED - Safe to push!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
