@echo off
setlocal
cd /d "%~dp0"
echo.
echo ========================================
echo    GE Login - Installation Script
echo ========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Python not found!
    echo.
    echo Please install Python 3.10+ first
    echo Download: https://www.python.org/downloads/
    echo.
    echo [IMPORTANT] Tick "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo [OK] Python %%v
echo.

:: Check if Chrome is installed
set "CHROME_FOUND=0"
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if "%CHROME_FOUND%"=="0" (
    echo [!] Google Chrome not found
    echo     Bot works best with Chrome. Install from: https://www.google.com/chrome/
    echo     You can also use --browser msedge or chromium as alternatives.
    echo.
) else (
    echo [OK] Google Chrome found
    echo.
)

:: Install Python dependencies
echo Installing Python packages...
pip install -r requirements.txt -q
if %ERRORLEVEL% NEQ 0 (
    echo [!] Some packages may have failed, retrying core packages...
    pip install playwright browser-cookie3 Pillow -q
)
echo [OK] Python packages installed
echo.

:: Install Playwright browsers
echo Installing Playwright browsers...
echo     (This may take 1-2 minutes)
python -m playwright install chromium
if %ERRORLEVEL% NEQ 0 (
    echo [X] Browser installation failed
    pause
    exit /b 1
)
echo [OK] Playwright browser installed
echo.

:: Create marker file
echo installed > .browsers_installed

echo.
echo ========================================
echo    [OK] Installation complete!
echo ========================================
echo.
echo How to use:
echo   1. Double-click START.bat to open the program
echo   2. Or run: python -m ui
echo.
echo Account file: IDGE.txt (one account per line, format: exe_id,password)
echo.
pause
