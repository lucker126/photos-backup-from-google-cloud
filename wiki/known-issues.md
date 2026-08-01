# Известные проблемы

## 1. Таймаут скачивания (критично)

```
TimeoutError: Timeout 120000ms exceeded while waiting for event "download"
```

**Причины:**
- Google Photos иногда не запускает скачивание после Shift+D
- Большие блоки (>100 фото) — Google долго формирует ZIP
- Rate limiting на стороне Google

**Workaround:** повторный запуск. Бот перепрыгнет уже скачанные блоки.

**Возможное решение:** увеличить таймаут до 300 сек или добавить retry с re-click.

## 2. Browser crash

```
Target page, context or browser has been closed
```

**Причины:**
- Нехватка RAM при больших ZIP
- Google закрывает соединение при подозрительной активности

**Workaround:** уменьшить `MAX_DELETE_BLOCKS_PER_RUN`, увеличить паузы.

## 3. Пустая галерея

```
wait_for_selector: элемент не найден
```

**Причины:**
- Google показал капчу (особенно в headless)
- Селекторы устарели после обновления UI

**Workaround:** проверить `HEADLESS_MODE=false`, пройти капчу вручную, обновить селекторы.

## 4. Дубли manifest

**Симптом:** `manifest_report.py --check-dups` находит одинаковые имена файлов.

**Причины:**
- Сбой во время записи manifest
- Ручное редактирование manifest

**Решение:**
```bash
python manifest_report.py --orphans --fix  # чистка осиротевших записей
```

## 5. AVHD-файлы

Google Photos иногда отдает `.avhd` вместо `.jpg` для HEIC. Обработка частично реализована в `_try_set_avhd_keys()`, но не всегда корректно распаковывается.

## 6. Селекторы ломаются после обновления Google Photos

**Симптом:** бот находит 0 блоков, хотя галерея есть.

**Диагностика:**
```python
page.query_selector_all('[role="checkbox"]')  # вернут ли непустой список?
```

**Решение:** обновить селекторы в `google_photos_bot.py` через DevTools.

## 7. Атрибут aria-checked не обновляется

После JS `click()` флажок визуально выбран, но `aria-checked` может оставаться `false` из-за React state. Используется визуальная проверка вместо атрибута.
