@echo off
cd /d "%~dp0"
echo Installing dashboard dependencies...
call npm install
if errorlevel 1 exit /b 1
echo Installing local API dependencies...
py -m pip install fastapi uvicorn requests
if errorlevel 1 exit /b 1
echo.
echo Setup complete. Start your existing OTrace service on port 8080, then run start-local-dashboard.bat
pause
