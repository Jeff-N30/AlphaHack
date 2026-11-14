@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Missing Python environment: %ROOT%\.venv
  echo Create it with: python -m venv .venv
  pause
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo pnpm was not found on PATH.
  echo Install pnpm or enable it with Corepack, then run this file again.
  pause
  exit /b 1
)

start "VisaRef Backend" cmd /k ""%ROOT%\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --app-dir "%ROOT%\backend" --port 8000"
start "VisaRef UI" cmd /k "cd /d "%ROOT%\frontend" && pnpm dev"

echo VisaRef services are starting.
echo Backend: http://127.0.0.1:8000
echo UI:      http://localhost:3000
echo Keep both service windows open while using the application.
endlocal
