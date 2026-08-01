# Конфигурация (`config.json`)

Файл создается автоматически при первом запуске из `DEFAULT_CONFIG` в коде. Пользовательские значения читаются из `config.json`, недостающие ключи заполняются дефолтами.

## Полная справка параметров

| Ключ | Тип | Default | Описание |
|------|-----|---------|----------|
| `DEST_DIR` | string | `"D:\\"` | Корневая папка для бэкапов. Внутри создаются `Фото Google YYYY/` |
| `PROFILE_DIR` | string | `"bot_profile"` | Директория профиля Chromium (persistent context). Хранит cookies/авторизацию |
| `TEMP_DIR` | string | `"temp_zip"` | Временная папка для скачанных ZIP перед распаковкой |
| `STATE_FILE` | string | `"backup_manifest.json"` | Файл состояния (manifest) |
| `DAYS_TO_KEEP_IN_CLOUD` | int | `180` | Файлы младше N дней не удаляются из облака |
| `STOP_AT_DATE` | string | `""` | Остановиться на дате (формат `YYYY-MM-DD`). Пустая строка = без лимита |
| `HEADLESS_MODE` | bool | `false` | Headless-режим браузера. ⚠️ Google детектирует headless — возможны капчи |
| `ALLOW_CLOUD_DELETE` | bool | `true` | Разрешить удаление файлов из облака |
| `DRY_RUN_DELETE` | bool | `true` | Режим имитации удаления (ничего не удаляется, только логируется) |
| `MAX_DELETE_BLOCKS_PER_RUN` | int | `1` | Максимум блоков на удаление за один запуск |
| `LOG_LEVEL` | string | `"WARNING"` | Уровень логов в `app.log` (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `SCROLL_STEP_PIXELS` | int | `500` | Шаг прокрутки галереи в пикселях |
| `SCROLL_WAIT_MS` | int | `1500` | Пауза после прокрутки (мс), чтобы React успел отрендерить |

## Alias-ключи

Код поддерживает синонимы (латиница/кириллица) для совместимости:

| Канонический | Alias |
|-------------|-------|
| `DEST_DIR` | `dest_dir` |
| `PROFILE_DIR` | `profile_dir` |
| `TEMP_DIR` | `temp_dir` |
| `STATE_FILE` | `state_file` |
| `DAYS_TO_KEEP_IN_CLOUD` | `days_to_keep_in_cloud` |
| `STOP_AT_DATE` | `stop_at_date` |
| `HEADLESS_MODE` | `headless_mode` |
| `ALLOW_CLOUD_DELETE` | `allow_cloud_delete` |
| `DRY_RUN_DELETE` | `dry_run_delete` |
| `MAX_DELETE_BLOCKS_PER_RUN` | `max_delete_blocks_per_run` |
| `LOG_LEVEL` | `log_level` |
| `SCROLL_STEP_PIXELS` | `scroll_step_pixels` |
| `SCROLL_WAIT_MS` | `scroll_wait_ms` |

При чтении значение из любого alias'а имеет приоритет над дефолтом.

## Пример `config.example.json`

```json
{
    "DEST_DIR": "D:\\",
    "PROFILE_DIR": "bot_profile",
    "TEMP_DIR": "temp_zip",
    "STATE_FILE": "backup_manifest.json",
    "DAYS_TO_KEEP_IN_CLOUD": 180,
    "STOP_AT_DATE": "",
    "HEADLESS_MODE": false,
    "ALLOW_CLOUD_DELETE": true,
    "DRY_RUN_DELETE": true,
    "MAX_DELETE_BLOCKS_PER_RUN": 1,
    "LOG_LEVEL": "WARNING",
    "SCROLL_STEP_PIXELS": 500,
    "SCROLL_WAIT_MS": 1500
}
```

## Рекомендации

### Первый запуск
```json
{
  "DRY_RUN_DELETE": true,
  "ALLOW_CLOUD_DELETE": false,
  "HEADLESS_MODE": false
}
```
Полностью безопасный режим — только скачивание и логирование.

### Боевой режим
```json
{
  "DRY_RUN_DELETE": false,
  "ALLOW_CLOUD_DELETE": true,
  "MAX_DELETE_BLOCKS_PER_RUN": 5
}
```
Постепенно увеличивайте `MAX_DELETE_BLOCKS_PER_RUN` после проверки стабильности.

### Отладка
```json
{
  "LOG_LEVEL": "DEBUG",
  "SCROLL_WAIT_MS": 3000
}
```
Больше деталей в логе, дольше паузы для медленных сетей.

## Переменные окружения

Не используются. Вся конфигурация — только через `config.json`.

## Известные особенности

- `STOP_AT_DATE` сравнивается по дате блока (`block_date <= stop_date` → стоп)
- `DAYS_TO_KEEP_IN_CLOUD` считается от `datetime.now()`, не от даты блока
- Если `ALLOW_CLOUD_DELETE=false`, то `DRY_RUN_DELETE` игнорируется (удаления не будет в любом случае)
