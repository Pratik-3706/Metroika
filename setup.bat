@echo off
setlocal

echo ====================================================
echo      METROIKA - Automated Setup Script
echo ====================================================
echo.

:: 1. Check for Python
echo [1/4] Checking for Python installation...
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not added to your PATH.
    echo Please install Python 3.9 or higher and try again.
    pause
    exit /b 1
)
echo Python found.
echo.

:: Navigate to backend
cd backend

:: 2. Create Virtual Environment
echo [2/4] Setting up Virtual Environment...
if not exist venv (
    python -m venv venv
    echo Virtual environment created at backend\venv.
) else (
    echo Virtual environment already exists, skipping creation.
)
echo.

:: 3. Install core dependencies
echo [3/4] Installing core backend dependencies...
.\venv\Scripts\python.exe -m pip install --upgrade pip >nul
.\venv\Scripts\python.exe -m pip install -r requirements.txt
echo Core dependencies installed.
echo.

:: 4. Detect GPU and install appropriate OCR package (PaddlePaddle)
echo [4/4] Checking system for NVIDIA GPU acceleration...
nvidia-smi >nul 2>nul
if %errorlevel% == 0 (
    echo - NVIDIA GPU Detected!
    echo - Installing GPU version of PaddlePaddle for OCR...
    .\venv\Scripts\python.exe -m pip install paddlepaddle-gpu
) else (
    echo - No NVIDIA GPU detected.
    echo - Installing CPU version of PaddlePaddle for OCR...
    .\venv\Scripts\python.exe -m pip install paddlepaddle
)
echo OCR packages installed.
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
    echo 3. Double-click start.bat to run the application!
) else (
    echo 1. Double-click start.bat to run the application!
)
echo.
pause
