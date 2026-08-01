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

### 3. Проверка авторизации (`ensure_authenticated`)
- Детерминированная race-логика (polling до ~10 сек): ждем первое из условий —
  появились чекбоксы галереи (`div[role="checkbox"][aria-label]:not([aria-checked="true"])`)
  ИЛИ обнаружена страница логина (URL содержит `accounts.google.com`/`/signin`, либо видно `input[type="email"]`)
- Если галерея — продолжаем сразу, без лишних ожиданий
- Если логин — ждем ручного входа/2FA до `AUTH_WAIT_TIMEOUT_MS` (из `config.json`, default 300000 мс),
  после редиректа на `photos.google.com/**` дополнительно дожидаемся рендера галереи (до 20 сек)
- Тот же хелпер вызывается и внутри основного цикла: если чекбоксы пропали и детектирована
  страница логина (сессия аннулирована посреди рана) — бот ждет повторный вход и продолжает
  с того же места, а не выходит с «галерея пуста»
- Если за таймаут не детектировано ни галереи, ни логина — выбрасывается `RuntimeError`, запуск завершается с ошибкой

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
