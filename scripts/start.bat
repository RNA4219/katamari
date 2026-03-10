@echo off
REM Katamari (Chainlit Fork) - Start Script
REM Usage: start.bat [port]
REM Auto-increments port if already in use.

setlocal enabledelayedexpansion

REM Set initial port
if "%1"=="" (
    set PORT=8787
) else (
    set PORT=%1
)

REM Find available port
:find_port
netstat -ano 2>nul | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    goto :port_found
)
echo Port %PORT% is in use, trying next...
set /a PORT+=1
if !PORT! gtr 9000 (
    echo ERROR: No available port found in range 8787-9000
    pause
    exit /b 1
)
goto :find_port

:port_found

REM Check if .env exists
if not exist ".env" (
    echo WARNING: .env file not found.
    echo Creating .env from template...
    copy config\env.example .env >nul 2>&1
    echo Please edit .env and configure your API keys.
    echo.
    pause
    exit /b 1
)

REM Check Python virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies if needed
pip install -q -r requirements.txt 2>nul

REM Start the application
echo.
echo Starting Katamari on http://localhost:%PORT%
echo Press Ctrl+C to stop.
echo.

chainlit run src/app.py --host 0.0.0.0 --port %PORT%

endlocal