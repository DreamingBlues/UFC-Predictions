@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Could not find the project virtual environment:
    echo %PYTHON%
    echo Create it and install backend\requirements.txt first.
    pause
    exit /b 1
)

start "UFC Predictions API" powershell.exe -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%ROOT%'; & '%PYTHON%' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002"

timeout /t 4 /nobreak >nul

start "UFC Predictions Frontend" powershell.exe -NoExit -ExecutionPolicy Bypass -Command "$env:NEXT_PUBLIC_API_URL='http://localhost:8002'; Set-Location -LiteralPath '%ROOT%frontend'; if (-not (Test-Path -LiteralPath 'node_modules\.bin\next.cmd')) { npm.cmd ci; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }; npm.cmd run dev"

timeout /t 8 /nobreak >nul
start "" "http://localhost:3000"

endlocal
