@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Google Photos Backup Bot

cd /d "%~dp0"

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

echo Не найден Python 3.
echo Установите Python с https://www.python.org/downloads/windows/
echo При установке обязательно включите галку "Add python.exe to PATH".
exit /b 1

:ensure_venv
if exist "venv\Scripts\python.exe" (
    echo Виртуальное окружение найдено.
    exit /b 0
)

echo Создаю виртуальное окружение venv...
%SYSTEM_PYTHON% -m venv venv
if errorlevel 1 (
    echo Не удалось создать виртуальное окружение.
    exit /b 1
)

echo Виртуальное окружение создано.
exit /b 0

:install_dependencies
echo.
echo Проверяю и устанавливаю зависимости...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Не удалось установить Python-зависимости.
    exit /b 1
)

echo.
echo Проверяю браузер Playwright...
"venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo Не удалось установить браузер Playwright Chromium.
    exit /b 1
)

exit /b 0

:ensure_config
echo.
if exist "config.json" (
    echo config.json найден.
    exit /b 0
)

echo Первый запуск: создаю config.json из config.example.json.
copy /Y "config.example.json" "config.json" >nul
if errorlevel 1 (
    echo Не удалось создать config.json.
    exit /b 1
)

echo.
echo Сейчас откроется config.json.
echo Проверьте как минимум:
echo   DEST_DIR - куда сохранять архив фото
echo   DAYS_TO_KEEP_IN_CLOUD - сколько дней держать фото в облаке
echo   DRY_RUN_DELETE - true для безопасного первого прогона
echo.
echo Закройте Блокнот после сохранения config.json.
start /wait notepad "config.json"

echo.
choice /C YN /M "Запустить бота сейчас"
if errorlevel 2 (
    echo Запуск отменен. Позже просто снова откройте start_bot.bat.
    exit /b 2
)

exit /b 0

:run_bot
echo.
echo Запускаю Google Photos Backup Bot...
echo Не закрывайте это окно до завершения работы.
echo ----------------------------------------
"venv\Scripts\python.exe" google_photos_bot.py
set "BOT_EXIT_CODE=%ERRORLEVEL%"
echo ----------------------------------------

if not "%BOT_EXIT_CODE%"=="0" (
    echo Бот завершился с кодом ошибки %BOT_EXIT_CODE%.
    echo Подробности смотрите в app.log.
    exit /b %BOT_EXIT_CODE%
)

echo Бот завершил работу успешно.
exit /b 0

:fail
echo.
echo Установка или запуск не удались.
echo Проверьте сообщения выше и файл app.log, если он уже был создан.

:finish
echo.
echo Нажмите любую клавишу, чтобы закрыть окно...
pause >nul
endlocal
