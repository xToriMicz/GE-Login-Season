@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul 2>nul
python -m ui
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error: Please run INSTALL.bat first
    pause
)
