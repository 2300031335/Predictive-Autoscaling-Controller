# PowerShell Local Run Script
Write-Host "Starting Predictive Autoscaler Service on http://127.0.0.1:8000..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
