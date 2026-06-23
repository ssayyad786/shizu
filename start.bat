@echo off
echo Starting Market Monitor...

start "Market Backend" cmd /k "cd /d %~dp0backend && py -m venv venv 2>nul && venv\Scripts\python.exe -m pip install -r requirements.txt -q && venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001"

timeout /t 3 /nobreak >nul

start "Market Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"

echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
pause
