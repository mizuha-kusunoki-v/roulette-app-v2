@echo off
setlocal
set "ROOT=%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv not found. Install it, open a new terminal, and run setup.bat again:
    echo   winget install astral-sh.uv
    goto :fail
)

where npm >nul 2>nul
if errorlevel 1 (
    echo npm not found. Install Node.js 18+ and run setup.bat again.
    goto :fail
)

echo [1/2] Backend: uv sync
pushd "%ROOT%vtuber-roulette-api"
call uv sync --locked
if errorlevel 1 (
    popd
    goto :fail
)
popd

echo [2/2] Frontend: npm ci
pushd "%ROOT%vtuber-roulette"
call npm ci
if errorlevel 1 (
    popd
    goto :fail
)
popd

echo Setup finished. Run start.bat to launch.
pause
exit /b 0

:fail
echo Setup failed.
pause
exit /b 1
