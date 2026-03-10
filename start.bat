@echo off
REM Katamari (Chainlit Fork) - Start Script
REM Usage: start.bat [port]

setlocal

REM Set default port
if "%1"=="" (
    set PORT=8787
) else (
    set PORT=%1
)

REM Check if .env exists
if not exist ".env" (
    echo WARNING: .env file not found.
    echo Please copy config\env.example to .env and configure your API keys.
    echo.
    copy config\env.example .env >nul 2>&1
    echo Created .env from template. Please edit it before running again.
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
echo Starting Katamari on http://localhost:%PORT%
echo Press Ctrl+C to stop.
echo.

chainlit run src/app.py --host 0.0.0.0 --port %PORT%

endlocal