@echo off
setlocal
set "ROOT=%~dp0.."

start "Backend" cmd /k "set PYTHONPATH=%ROOT% && cd /d %ROOT% && python -m uvicorn Iot_Simulator.api_server.main:app --port 8090 --reload"
timeout /t 2 >nul
start "Frontend" cmd /k "cd /d %ROOT%\Iot_Simulator\simulator-web && npm run dev"

echo Both services started.
echo Backend:  http://localhost:8090
echo Frontend: http://localhost:5173
