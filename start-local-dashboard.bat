@echo off
cd /d "%~dp0"
if not exist node_modules (
 echo Dashboard dependencies are missing. Run setup-local.bat first.
 pause
 exit /b 1
)
start "OTrace Dashboard API" cmd /k "cd /d ""%~dp0"" && py -m uvicorn local_api:app --host 127.0.0.1 --port 8090"
set VITE_OTRACE_API_BASE=http://127.0.0.1:8090
start "OTrace Dashboard" cmd /k "cd /d ""%~dp0"" && npm run dev -- --host 127.0.0.1 --port 5173"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5173
