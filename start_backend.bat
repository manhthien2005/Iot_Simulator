@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%"
uvicorn Iot_Simulator.api_server.main:app --port 8090 --reload
