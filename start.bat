@echo off
set "ROOT=%~dp0"

start "Roulette API 8000" /D "%ROOT%vtuber-roulette-api" cmd /k ".venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000 --reload"
start "Roulette Frontend 3000" /D "%ROOT%vtuber-roulette" cmd /k "set BROWSER=none&& npm start"

echo Started.
echo   Admin : http://localhost:3000/
echo   OBS   : http://localhost:3000/viewer/result
timeout /t 5 >nul
