# Основной цикл работы (workflow)

## Точка входа

`run()` в `google_photos_bot.py` — единственная публичная функция оркестратора.

## Этапы выполнения

### 1. Инициализация
```
load_config() → setup_logging() → create_report_dirs() → load_manifest()
```
- Создаются `DEST_DIR`, `TEMP_DIR`, директория логов
- Загружается manifest (если не существует — создается пустой v3)

### 2. Запуск браузера
```python
p.chromium.launch_persistent_context(
    user_data_dir=PROFILE_DIR,
    headless=HEADLESS_MODE,
    viewport={'width': 1280, 'height': 800},
    ...
)
```
- Persistent context сохраняет cookies между запусками
- Открывается `https://photos.google.com/`

### 3. Проверка авторизации
- Ждем `input[type="email"]` или `textarea[aria-label]` до 120 секунд
- Если email-поле — это страница логина → ждем ручного входа 300 сек
- Если нет элементов — считаем авторизованным

### 4. Поиск блоков
Цикл сканирования галереи:
```
while not stop_condition:
    scroll(SCROLL_STEP_PIXELS)
    sleep(SCROLL_WAIT_MS)
    query_selector_all('[role="checkbox"][aria-label]')
    если checkbox'ей нет 5 скроллов подряд → stop
    если дата блока <= STOP_AT_DATE → stop
```

Для каждого checkbox:
- `aria-label` → парсинг даты → `block_id`
- Пропуск если уже `files_verified=true` и не старше `DAYS_TO_KEEP_IN_CLOUD`
- Пропуск если дата покрыта группой (`date_coverage`)

### 5. Обработка блока
```
google_photos_select_and_download_block(checkbox, block_id)
  → клик (3 попытки + JS fallback)
  → Shift+D (скачивание)
  → _parse_additional_metadata() → count
  → expect_download(timeout=120s)
  → save ZIP → TEMP_DIR
  → handle_download_and_verify(zip_path, block_id, block_date)
    → extractall(TEMP_DIR)
    → для каждого файла:
      → correct_file_date() → EXIF/имя → year
      → копирование в DEST_DIR/Фото Google YYYY/
      → recursive dedup (проверка по sha256 в других годах)
      → get_file_hash() → сверка
    → записать в manifest
    → удалить ZIP
  → если files_verified и старше DAYS_TO_KEEP_IN_CLOUD:
    → select_and_delete_group() → удаление из облака
```

### 6. Завершение
- Итоговый отчет в лог/консоль: скачано, удалено, ошибок, период дат
- `context.close()` — браузер закрывается

## Обработка ошибок

| Ошибка | Реакция |
|--------|---------|
| Таймаут `expect_download` | Лог ERROR, блок пропускается, manifest не обновляется |
| Browser crash | `try/except` вокруг всего цикла, trace в лог, выход |
| Нет checkbox'ей 5 скроллов | Считаем конец галереи, выходим из цикла |
| `partial=true` | Блок помечается, файлы с ошибками перечисляются |

## Идемпотентность

- Повторный запуск **не скачивает** уже верифицированные блоки
- `files_verified=false` блоки **переобрабатываются** (безопасно)
- Manifest — единственный критерий "уже сделано"

## Потоки и асинхронность

- **Нет**. Sync API Playwright, один цикл, один поток.
- Ожидание — только таймауты Playwright (`wait_for_selector`, `expect_download`, `sleep`).

## Границы цикла

- Максимум блоков на удаление: `MAX_DELETE_BLOCKS_PER_RUN` (default=1)
- Максимум скроллов без результатов: 5
- Остановка по дате: `STOP_AT_DATE`
