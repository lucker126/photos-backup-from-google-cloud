# Операционная документация

## manifest_report.py — аналитика без браузера

Инструмент для offline-анализа `backup_manifest.json`.

### Базовое использование

```bash
venv\Scripts\activate
python manifest_report.py                    # сводка + последние 10 записей
python manifest_report.py --check-dups      # найти дубликаты имён файлов
python manifest_report.py --orphans         # найти осиротевшие item-записи
python manifest_report.py --orphans --fix   # удалить осиротевшие записи
python manifest_report.py --full-report     # полный отчёт
```

### Примеры вывода

**Сводка (без аргументов):**
```
=== СВОДКА ===
Всего блоков: 127
Файлов: 3,451
Объём: 12.4 GB
По годам: 2019=45, 2020=89, 2023=2,112, 2024=1,205
Удалено из облака: 98 блоков
Ожидает удаления: 29 блоков
```

**--check-dups:**
```
Дубликаты имени 'IMG_001.jpg':
  - D:\Фото Google 2023\IMG_001.jpg (sha256: a1b2...)
  - D:\Фото Google 2023\IMG_001.jpg (sha256: a1b2...)  ← идентичный хеш = безопасно
```

### Поля manifest

| Поле | Описание |
|------|----------|
| `block_id` | `GROUP: text` или `ITEM: filename` |
| `files_verified` | Все файлы проверены SHA-256 |
| `deleted_from_cloud` | Удален ли из Google Photos |
| `partial` | Были ли ошибки верификации |

## Устранение неполадок

### Таймаут скачивания

```
TimeoutError: Timeout 120000ms exceeded while waiting for event "download"
```

**Диагностика:**
1. Откройте `app.log` → найдите блок перед ошибкой
2. Проверьте `temp_zip/` — есть ли недокачанный ZIP?

**Решение:**
- Перезапустите бота (идемпотентность позволяет)
- Увеличьте таймаут в `google_photos_bot.py`: `timeout=300000`

### Browser Crash

```
Target page, context or browser has been closed
```

**Решение:**
- Уменьшите `MAX_DELETE_BLOCKS_PER_RUN` до 1
- Увеличьте `SCROLL_WAIT_MS` до 3000
- Убедитесь, что `HEADLESS_MODE=false`

### Пустая галерея

Бот не находит ни одного checkbox.

**Диагностика:**
```python
# В консоли браузера (F12):
document.querySelectorAll('[role="checkbox"]').length  // 0?
```

**Решение:**
1. Проверьте, не показал ли Google капчу
2. Обновите селекторы (Google меняет UI)
3. Убедитесь, что окно Chrome не minimized (иногда мешает рендеру)

## Чтение app.log

Формат: `YYYY-MM-DD HH:MM:SS - LEVEL - message`

### Уровни и что искать

| Уровень | Когда | Действие |
|---------|-------|----------|
| `INFO` | Скачано, удалено, отчет | Норма |
| `WARNING` | Retry клика, partial | Мониторить |
| `ERROR` | Таймаут, crash, corrupt ZIP | Требует внимания |

### Полезные паттерны

```bash
# Все скачанные блоки
grep -i "скачан" app.log

# Все ошибки
grep -i "ERROR" app.log

# Dry-run удаления
grep -i "DRY-RUN" app.log

# Статистика по запуску (последний)
grep -A 20 "ИТОГОВЫЙ ОТЧЕТ" app.log | tail -20
```

## Плановые задачи

### Ежедневный запуск (Task Scheduler)

```powershell
# Создать задачу
schtasks /create /tn "GooglePhotosBackup" /tr "e:\VSCode\photos-backup\start_bot.bat" /sc daily /st 02:00
```

### Чистка старых логов

```python
# logging.RotatingFileHandler автоматически ротирует
# Макс: 5MB × 3 файла = 15MB истории
```

### Бэкап manifest

```bash
copy backup_manifest.json backup_manifest_%date%.json
```
