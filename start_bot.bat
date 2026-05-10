@echo off
setlocal EnableExtensions
title Google Photos Backup Bot

cd /d "%~dp0"

if /I "%~1"=="--check" (
    echo start_bot.bat check ok
    exit /b 0
)

echo ========================================
echo Google Photos Backup Bot
echo ========================================
echo.

call :find_python || goto fail
call :ensure_venv || goto fail
call :install_dependencies || goto fail
call :ensure_config
if errorlevel 2 goto finish
if errorlevel 1 goto fail
call :run_bot
goto finish

:find_python
if exist "venv\Scripts\python.exe" (
    set "SYSTEM_PYTHON=venv\Scripts\python.exe"
    exit /b 0
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PYTHON=py -3"
    exit /b 0
)

python --version >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PYTHON=python"
    exit /b 0
)

echo Python 3 was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo During installation, enable "Add python.exe to PATH".
exit /b 1

:ensure_venv
if exist "venv\Scripts\python.exe" (
    echo Virtual environment found.
    exit /b 0
)

echo Creating virtual environment: venv
%SYSTEM_PYTHON% -m venv venv
if errorlevel 1 (
    echo Failed to create virtual environment.
    exit /b 1
)

echo Virtual environment created.
exit /b 0

:install_dependencies
echo.
echo Checking Python dependencies...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install Python dependencies.
    exit /b 1
)

echo.
echo Checking Playwright Chromium...
"venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo Failed to install Playwright Chromium.
    exit /b 1
)

exit /b 0

:ensure_config
echo.
if exist "config.json" (
    echo config.json found. Existing config will not be changed.
    exit /b 0
)

echo First run: creating config.json from config.example.json.
copy /Y "config.example.json" "config.json" >nul
if errorlevel 1 (
    echo Failed to create config.json.
    exit /b 1
)

echo.
echo config.json will open in Notepad now.
echo Please check at least these settings:
echo   DEST_DIR - where the local photo archive will be stored
echo   DAYS_TO_KEEP_IN_CLOUD - how many days photos stay in Google Photos
echo   DRY_RUN_DELETE - keep true for the first safe run
echo.
echo Save config.json and close Notepad when ready.
start /wait notepad "config.json"

echo.
choice /C YN /M "Start the bot now"
if errorlevel 2 (
    echo Start cancelled. Run start_bot.bat again when ready.
    exit /b 2
)

exit /b 0

:run_bot
echo.
echo Starting Google Photos Backup Bot...
echo Do not close this window until the bot finishes.
echo ----------------------------------------
"venv\Scripts\python.exe" google_photos_bot.py
set "BOT_EXIT_CODE=%ERRORLEVEL%"
echo ----------------------------------------

if not "%BOT_EXIT_CODE%"=="0" (
    echo Bot finished with error code %BOT_EXIT_CODE%.
    echo See app.log for details.
    exit /b %BOT_EXIT_CODE%
)

echo Bot finished successfully.
exit /b 0

:fail
echo.
echo Setup or launch failed.
echo Check the messages above and app.log if it already exists.

:finish
echo.
echo Press any key to close this window...
pause >nul
endlocal
