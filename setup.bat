@echo off
setlocal
echo [*] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found! Please install it from python.org
    pause & exit /b
)

echo [*] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

echo [*] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo [!] Installation failed.
    pause & exit /b
)

echo [*] Creating launch script...
(
echo @echo off
echo call venv\Scripts\activate
echo python autocatch.py
echo pause
) > run.bat

echo.
echo [!] Setup complete! Run 'run.bat' to start the bot.
pause
