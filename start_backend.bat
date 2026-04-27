@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
uvicorn api_server.main:app --port 8090 --reload
