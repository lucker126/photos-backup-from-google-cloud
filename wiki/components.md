# Компоненты

## google_photos_bot.py (854 строки)

Основной модуль. Sync API Playwright.

### Утилиты
| Функция | Назначение |
|---------|-----------|
| `load_config()` | Читает `config.json`, дополняет дефолтами (latin/cyrillic aliases) |
| `get_file_hash(path)` | SHA-256 хеш файла для верификации |
| `create_report_dirs()` | Создает `DEST_DIR` и `TEMP_DIR` |
| `setup_logging()` | RotatingFileHandler → `app.log` + INFO в консоль |
| `load_manifest/save_manifest()` | Версионированная работа с state-file (legacy миграция, uniq по block_id) |
| `get_block_id()` | Ключ блока: `"GROUP: <text>"` или `"ITEM: <text>"` |
| `get_verified_block_ids_from_manifest()` | block_id, где все файлы verified-local |

### Дата/текст
| Функция | Назначение |
|---------|-----------|
| `parse_date_from_aria_label()` | RU/EN/Cyrillic месяцы → `datetime`; поддерживает 18 форматов |
| `normalize/standardize` | Приведение текста для сравнения |

### Файловая обработка
| Функция | Назначение |
|---------|-----------|
| `correct_file_date()` | EXIF (PIL) + RU/EN filename → правильные даты файлов |
| `handle_download_and_verify()` | Распаковка ZIP, дедупликация recursive, cross-year dedup, partial-детекция |
| `_try_set_avhd_keys()` | AVHD-специфика Google Photos |

### UI-автоматизация
| Функция | Назначение |
|---------|-----------|
| `parse_manual_date_from_display_article()` | Находит DOM-элементы без `aria-label` через JS evaluate |
| `google_photos_select_and_download_block()` | Клик с 3 попытками + JS fallback, Shift+D, таймаут 120s |
| `_parse_additional_metadata()` | Извлекает "Фото · X items" → count |
| `select_and_delete_group()` | JS evaluate для поиска-выбора-удаления группы |

### Оркестратор
| Функция | Назначение |
|---------|-----------|
| `run()` | Главный цикл: init → check auth → scan blocks → process → report |

## manifest_report.py (389 строк)

Offline-анализ `backup_manifest.json`. **Не требует браузера.**

```bash
python manifest_report.py                    # сводка + история
python manifest_report.py --check-dups      # дубликаты по именам
python manifest_report.py --fields          # топ значений полей
python manifest_report.py --orphans --fix   # удаление осиротевших записей
python manifest_report.py --full-report     # все действия
```

| Функция | Описание |
|---------|----------|
| `load_manifest_tolerant()` | Чтение с fallback'ами для legacy форматов |
| `_is_valid_entry()` | Пропускает пустые/невалидные записи |
| `cmd_summary()` | Общая статистика, файлы, распределение по годам |
| `cmd_field_show()` | Топ-N уникальных значений любого поля |
| `cmd_check_dups()` | Дубликаты имён файлов |
| `cmd_orphans()` | Осиротевшие item-записи (нет группы на дату) |
| `cmd_history()` | Последние N по дате скачивания |

## start_bot.bat

Windows batch wrapper:
1. Создает `venv` если не существует
2. `pip install -r requirements.txt`
3. `playwright install chromium`
4. Запускает `python google_photos_bot.py`
5. При ошибке показывает последние 20 строк `app.log`

## config.json

Создается при первом запуске на основе `DEFAULT_CONFIG` в коде. См. [[config]].

## backup_manifest.json

Состояние проекта. См. [[manifest-schema]].

## app.log

RotatingFileHandler: макс 5MB, 2 backup-файла. Формат: `%(asctime)s - %(levelname)s - %(message)s`.
