@echo off
chcp 65001 >nul
echo ========================================
echo LangGraph Studio Quickstart
echo ========================================
echo.

REM Change to project root
cd /d %~dp0

REM Activate virtual environment if exists
if exist "backend\venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call backend\venv\Scripts\activate.bat
)

REM Check if LangGraph CLI is installed
python -c "import langgraph_cli" 2>nul
if errorlevel 1 (
    echo LangGraph CLI not found. Installing...
    pip install -U "langgraph-cli[inmem]"
)

REM Run Python script to handle .env file encoding and start server
python start-langgraph-studio.py
