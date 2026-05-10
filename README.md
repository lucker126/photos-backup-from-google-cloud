# Google Photos Backup & Sync Bot

Локальный Windows-бот для резервного копирования фото и видео из Google Photos с последующей безопасной очисткой облака.

Идея простая: все найденные медиафайлы сохраняются в локальный архив, а из Google Photos удаляются только те блоки, которые уже подтверждены локальным manifest и старше `DAYS_TO_KEEP_IN_CLOUD`.

## Быстрый Старт

Самый простой способ для обычного пользователя:

1. Установите Python 3 с официального сайта: https://www.python.org/downloads/windows/
2. При установке Python обязательно включите галку `Add python.exe to PATH`.
3. Скачайте архив проекта из GitHub Releases и распакуйте его в удобную папку.
4. Запустите `start_bot.bat` двойным кликом.
5. При первом запуске откроется `config.json`. Настройте его, сохраните и закройте Блокнот.
6. Разрешите запуск бота в окне `start_bot.bat`.
7. При первом открытии браузера войдите в Google-аккаунт вручную, если бот попросит авторизацию.

`start_bot.bat` сам создает виртуальное окружение `venv`, устанавливает зависимости из `requirements.txt`, ставит браузер Playwright Chromium, создает `config.json` из `config.example.json` и запускает `google_photos_bot.py`.

## Что Настроить

Главный файл настроек: `config.json`. Он создается автоматически при первом запуске.

В первую очередь проверьте:

- `DEST_DIR`: куда сохранять локальный архив фото и видео.
- `DAYS_TO_KEEP_IN_CLOUD`: сколько дней фото остаются в Google Photos.
- `DRY_RUN_DELETE`: безопасный режим удаления. Для первого прогона лучше оставить `true`.
- `ALLOW_CLOUD_DELETE`: разрешает реальное удаление из облака.
- `MAX_DELETE_BLOCKS_PER_RUN`: лимит удаляемых блоков за запуск, `0` означает без лимита.
- `LOG_LEVEL`: подробность логов. `WARNING` пишет старт, итог и проблемы; `INFO` добавляет скачивания и удаления; `DEBUG` включает подробную UI-механику.
- `SCROLL_STEP_PIXELS`: шаг прокрутки Google Photos. По умолчанию `500`.
- `SCROLL_WAIT_MS`: пауза после прокрутки для подгрузки новых элементов.

Безопасный первый запуск:

```json
"DRY_RUN_DELETE": true
```

Боевой запуск после проверки логов:

```json
"DRY_RUN_DELETE": false
```

## Обычный Запуск

После первой установки достаточно снова запускать:

```powershell
start_bot.bat
```

Если нужно вручную запустить из консоли:

```powershell
venv\Scripts\python.exe google_photos_bot.py
```

## Безопасность Удаления

Удаление из Google Photos выполняется только если одновременно выполнены условия:

- Блок старше `DAYS_TO_KEEP_IN_CLOUD`.
- Локальная копия уже скачана.
- Файлы проверены по SHA-256 и записаны в `backup_manifest.json`.
- Для групповых блоков одиночные item-записи корректно покрыты группой.
- После клика удаления Google Photos подтвердил исчезновение исходного checkbox из DOM.

Если скачивание было прервано, файл не считается подтвержденным и не будет удален из облака.

## Manifest И Отчеты

`backup_manifest.json` хранит состояние архива: подтвержденные файлы, покрытые даты, удаленные блоки и ошибки.

Посмотреть сводку:

```powershell
venv\Scripts\python.exe manifest_report.py
```

Полезные команды:

```powershell
venv\Scripts\python.exe manifest_report.py --delete-candidates
venv\Scripts\python.exe manifest_report.py --unverified
venv\Scripts\python.exe manifest_report.py --errors
venv\Scripts\python.exe manifest_report.py --date 2025-11-11
venv\Scripts\python.exe manifest_report.py --as-of 2026-05-17 --delete-candidates
```

## Файлы Проекта

- `start_bot.bat`: единый установщик и запускатель для Windows.
- `google_photos_bot.py`: основной бот.
- `manifest_report.py`: локальная аналитика manifest без запуска браузера.
- `config.example.json`: шаблон настроек.
- `config.json`: ваши локальные настройки, не попадает в git.
- `backup_manifest.json`: локальное состояние архива, не попадает в git.
- `app.log`: лог работы, не попадает в git.
- `bot_profile`: профиль браузера с Google-сессией, не попадает в git.

## Важно

Это браузерная автоматизация Google Photos, поэтому интерфейс Google может меняться. Перед первым боевым удалением лучше сделать один прогон с `DRY_RUN_DELETE=true`, посмотреть `app.log` и отчет `manifest_report.py`.
