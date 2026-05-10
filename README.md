# Google Photos Backup Bot

Локальный Python-скрипт для резервного копирования Google Photos на диск и последующей очистки облака по правилу `DAYS_TO_KEEP_IN_CLOUD`.

## Что делает

- Скачивает блоки фото и видео из Google Photos через Playwright.
- Раскладывает файлы по папкам вида `Фото Google 2026`.
- Ведет локальный `backup_manifest.json` с подтвержденными блоками.
- Запоминает даты, уже покрытые проверенной групповой загрузкой, чтобы не скачивать одиночные фото из этой группы повторно.
- Удаляет из облака только те блоки, которые старше `DAYS_TO_KEEP_IN_CLOUD` и уже подтверждены в локальном архиве.
- Не считает старый `SKIP_PERIOD` доказательством сохранности файлов.

## Установка

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Если используется системный Chrome, скрипт запускает канал `chrome`.

## Настройка

Создайте локальный `config.json` на основе `config.example.json`.

Ключевые параметры:

- `DEST_DIR`: корневая папка для архива.
- `PROFILE_DIR`: профиль браузера с Google-сессией.
- `TEMP_DIR`: временная папка для загрузок и распаковки.
- `STATE_FILE`: manifest состояния, по умолчанию `backup_manifest.json`.
- `DAYS_TO_KEEP_IN_CLOUD`: сколько дней фото остаются в Google Photos.
- `ALLOW_CLOUD_DELETE`: включает реальное удаление из облака.
- `DRY_RUN_DELETE`: оставляет удаление выключенным, но показывает, что было бы удалено.
- `MAX_DELETE_BLOCKS_PER_RUN`: лимит удаляемых блоков за запуск, `0` означает без лимита.

## Запуск

```powershell
venv\Scripts\activate
python google_photos_bot.py
```

Или через `start_bot.bat`.

При первом запуске может потребоваться ручной вход в Google. Сессия сохраняется в `bot_profile`.

## Отчет по manifest

`manifest_report.py` читает только локальные `config.json` и `backup_manifest.json`. Он не запускает браузер, ничего не скачивает и не удаляет.

```powershell
python manifest_report.py
python manifest_report.py --date 2025-11-11
python manifest_report.py --unverified
python manifest_report.py --errors
python manifest_report.py --delete-candidates
python manifest_report.py --as-of 2026-05-17 --delete-candidates
```

Полезные режимы:

- `--date YYYY-MM-DD`: показать все блоки конкретной даты.
- `--delete-candidates`: показать подтвержденные блоки старше `DAYS_TO_KEEP_IN_CLOUD`, без дублей одиночных item-записей, покрытых группами.
- `--all-delete-candidates`: показать сырые candidate-записи, включая item-записи, покрытые группами.
- `--blocked-delete`: показать старые блоки, которые нельзя удалять, потому что архив не подтвержден.
- `--limit N`: увеличить количество строк в списках.

## Важная логика безопасности

`DAYS_TO_KEEP_IN_CLOUD` определяет, какие блоки пора удалить из облака. Но само удаление разрешается только после локальной проверки файлов и записи `files_verified` в manifest.

Если блок старше порога, но локальная копия не подтверждена, скрипт сначала скачает и проверит блок. Если скачать или проверить не удалось, удаление не выполняется.

Если дневная группа успешно скачана архивом и проверена, одиночные фото этой даты считаются покрытыми этой группой и не скачиваются повторно.

Для первого запуска после перехода на manifest разумно временно поставить:

```json
"DRY_RUN_DELETE": true
```

Так можно собрать состояние и посмотреть отчет без риска очистки облака.
