@echo off
setlocal
set "ROOT=%~dp0"
rem Strip trailing backslash for cleaner PYTHONPATH
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

start "Backend" cmd /k "set PYTHONPATH=%ROOT% && cd /d %ROOT% && python -m uvicorn api_server.main:app --port 8090 --reload"
timeout /t 2 >nul
start "Frontend" cmd /k "cd /d %ROOT%\simulator-web && npm run dev"

echo Both services started.
echo Backend:  http://localhost:8090
echo Frontend: http://localhost:5173
