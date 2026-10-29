# PowerShell Setup Script for Windows
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Predictive Autoscaler Environment Setup (Windows)        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "[1/4] Found Astral uv package manager." -ForegroundColor Green
    Write-Host "Creating Python 3.11 virtual environment..." -ForegroundColor Yellow
    uv venv --python 3.11 .venv
    Write-Host "Installing pinned dependencies with uv..." -ForegroundColor Yellow
    uv pip install -r requirements.txt --python .venv\Scripts\python.exe
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "[1/4] Found Python. Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
} else {
    Write-Host "[ERROR] Neither uv nor python was found on PATH." -ForegroundColor Red
    exit 1
}

# 2. Generate Sample Workload Traces
Write-Host "[2/4] Generating synthetic benchmark workloads..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe workloads/workload_generator.py --output-dir ./data/sample

# 3. Train Baseline Forecast Models
Write-Host "[3/4] Training Prophet and LSTM models on benchmark traces..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe scripts/train_model.py

# 4. Run Verification Tests
Write-Host "[4/4] Executing verification test suite..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m pytest tests/ -v

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Setup complete! To start the service locally, run:       " -ForegroundColor Green
Write-Host "   .\scripts\start_local.ps1                              " -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Green
