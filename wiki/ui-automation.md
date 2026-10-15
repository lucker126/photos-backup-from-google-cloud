# UI-автоматизация (Playwright)

## Подход

Playwright sync API + Chromium persistent context. Никакого headless-режима в production — Google детектирует и показывает капчи/пустые галереи.

## Запуск браузера

```python
p.chromium.launch_persistent_context(
    user_data_dir=PROFILE_DIR,      # cookies сохраняются между запусками
    headless=HEADLESS_MODE,          # False по умолчанию
    viewport={'width': 1280, 'height': 800},
    device_scale_factor=1,
    args=['--disable-blink-features=AutomationControlled']  # скрываем флаг автоматизации
)
```

- `user_data_dir` — директория профиля Chrome (кэш, cookies, localStorage)
- `--disable-blink-features=AutomationControlled` — маскирует Playwright от детекторов Google

## Селекторы

| Элемент | Селектор | Почему |
|---------|----------|--------|
| Чекбокс блока | `[role="checkbox"][aria-label]` | Google Photos использует ARIA-роли |
| Заголовок группы | `div[role="heading"]` | Заголовки дат в виртуальном скролле |
| Email поле | `input[type="email"]` | Страница логина Google |
| Textarea поиска | `textarea[aria-label]` | Альтернативный индикатор авторизации |

## Скролл виртуального DOM

Google Photos использует **React Virtual DOM** — элементы создаются/удаляются при прокрутке. Алгоритм:

```python
page.mouse.wheel(0, SCROLL_STEP_PIXELS)  # шаг из конфига
page.wait_for_timeout(SCROLL_WAIT_MS)    # ждем рендер
checkboxes = page.query_selector_all('[role="checkbox"][aria-label]')
```

- `SCROLL_STEP_PIXELS=500` — шаг прокрутки
- `SCROLL_WAIT_MS=1500` — пауза для React
- Если 5 скроллов подряд не дают новых checkbox'ей → конец галереи

## Клик по чекбоксу

### 3 попытки + JS fallback

```python
for attempt in range(3):
    try:
        checkbox.scroll_into_view_if_needed()
        checkbox.click()
        break
    except:
        if attempt == 2:
            # JS fallback: dispatchEvent через page.evaluate()
            page.evaluate('el => el.click()', checkbox)
```

### Почему JS fallback

Иногда Playwright не может кликнуть из-за:
- Overlay от Google (анимация, тултип)
- Элемент вне viewport после scroll
- React re-render между scroll и click

`page.evaluate('el => el.click()')` — программный клик, первое событие mousedown/up/click напрямую в DOM.

## Скачивание

### Shift+D механика и Retry

```python
download_path = download_block_with_retry(
    page=page,
    static_cb=static_cb,
    safe_label=safe_label,
    temp_dir=TEMP_DIR,
    timeout_ms=DOWNLOAD_TIMEOUT_MS,
    max_retries=DOWNLOAD_MAX_RETRIES
)
```

- Выбранные элементы скачиваются по шорткату `Shift+D`
- Playwright перехватывает скачивание через `page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS)`
- При возникновении таймаута или ошибки:
  1. Проверяется сессия Google (если произошел разлогин mid-run — вызывается `ensure_authenticated`)
  2. Восстанавливается фокус окна и body
  3. Делается re-click чекбокса (`select_block_checkbox` со снятием и повторным выставлением галочки)
  4. Повторяется нажатие `Shift+D` в пределах `DOWNLOAD_MAX_RETRIES` (дефолт 3)
- Если Google отдает 0-байтовый файл, он удаляется, и инициируется повторная попытка.
- Таймаут по умолчанию 120 с (`DOWNLOAD_TIMEOUT_MS: 120000`), настраивается в `config.json`.

## Удаление

### Механика удаления и подтверждения

1. Проверяется состояние `aria-checked` чекбокса блока. Если Google снял выделение, вызывается `select_block_checkbox`.
2. Нажимается кнопка корзины в тулбаре (`page.locator('button[aria-label="Удалить"], button[aria-label="В корзину"]')`) с fallback через `evaluate("btn => btn.click()")`.
3. Вызывается `confirm_delete_if_required`:
   - Динамически считывает диалог `div[role="dialog"]`.
   - Ищет действие подтверждения (кнопки с текстом «В корзину», «Удалить», «Переместить», «Move», «Delete», «Trash»).
   - Нажимает подтверждение и ожидает скрытия окна.
4. Вызывается `wait_for_delete_completion`:
   - Опрашивает DOM с шагом 500 мс (до 30 с) до исчезновения чекбокса из DOM.
   - Если диалог появился с задержкой уже в процессе ожидания — повторно перехватывает и подтверждает его.
   - При сбое сохраняет отладочный скриншот `delete_error.png`.

## Логирование UI-событий

В `app.log` пишется:
- `INFO` — успешные действия (скачано, удалено)
- `WARNING` — повторные попытки клика, частичная верификация
- `ERROR` — таймауты, crash, ошибки парсинга

## Меры против детекции

1. **Persistent profile** — настоящий Chrome с cookies
2. **Viewport 1280x800** — стандартный десктопный размер
3. **No headless** — `HEADLESS_MODE=false` в рекомендованной конфигурации
4. **AutomationControlled off** — скрываем флаг webdriver
