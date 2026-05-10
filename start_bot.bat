@echo off
title Google Photos Sync Bot

REM Переходим в папку, где лежит сам батник
cd /d "%~dp0"

REM Проверяем, существует ли папка с окружением
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found in %~dp0venv
    echo Please create it first.
    echo.
    pause
    exit /b
)

REM Активируем виртуальное окружение (используем call, чтобы скрипт не прервался)
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Запускаем скрипт
echo.
echo Starting Google Photos Backup Bot...
echo Please do not close this window.
echo ----------------------------------------
python google_photos_bot.py
echo ----------------------------------------

REM Деактивируем окружение после завершения (хороший тон)
deactivate

REM Оставляем консоль открытой, чтобы прочитать логи в случае падения или завершения
echo.
echo Process finished. Press any key to exit...
pause >nul