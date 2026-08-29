@echo off
setlocal

echo ====================================================
echo      METROIKA - Automated Setup Script
echo ====================================================
echo.

:: 1. Check for Python
echo [1/5] Checking for Python 3.10 or 3.11 installation...
py -3.10 --version >nul 2>nul
if %errorlevel% neq 0 (
    py -3.11 --version >nul 2>nul
    if %errorlevel% neq 0 (
        echo ERROR: Python 3.10 or 3.11 is not installed.
        echo Please install Python 3.10 or 3.11. PaddleOCR does not support Python 3.13 yet.
        pause
        exit /b 1
    ) else (
        set PY_CMD=py -3.11
    )
) else (
    set PY_CMD=py -3.10
)
echo Compatible Python found!
echo.

:: Navigate to backend
cd backend

:: 2. Create Virtual Environment
echo [2/5] Setting up Virtual Environment...
if not exist venv (
    %PY_CMD% -m venv venv
    echo Virtual environment created at backend\venv.
) else (
    echo Virtual environment already exists, skipping creation.
)
echo.

:: 3. Install core dependencies
echo [3/5] Installing core backend dependencies...
.\venv\Scripts\python.exe -m pip install --upgrade pip >nul
.\venv\Scripts\python.exe -m pip install -r requirements.txt
echo Core dependencies installed.
echo.

:: 4. Detect GPU and install appropriate PaddlePaddle
echo [4/5] Running Hardware Detection and AI Engine Setup...
.\venv\Scripts\python.exe install_env.py
echo.

:: 5. Pre-download AI Models
echo [5/5] Pre-downloading OCR Models so the server starts instantly...
.\venv\Scripts\python.exe download_models.py
echo.

cd ..

echo ====================================================
echo                   SETUP COMPLETE!
echo ====================================================
echo.
echo Next Steps:
if not exist backend\.env (
    echo 1. Copy backend\.env.example to backend\.env
    echo 2. Open backend\.env and add your API Keys.
    echo    ^(AI is OPTIONAL - the system works without it!^)
    echo 3. Double-click start.bat to run the application!
) else (
    echo 1. Double-click start.bat to run the application!
)
echo.
pause
