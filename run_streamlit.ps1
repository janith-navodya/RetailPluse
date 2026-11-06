# RetailPulse DI - Streamlit Launcher
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "         Launching RetailPulse Decision Intelligence Portal" -ForegroundColor Green
Write-Host "===============================================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$AppPy = Join-Path $PSScriptRoot "app.py"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found at $VenvPython. Please verify .venv exists."
    exit 1
}

Write-Host "Starting Streamlit web interface..." -ForegroundColor Yellow
& $VenvPython -m streamlit run $AppPy
