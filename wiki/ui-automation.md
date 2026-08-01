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

### Shift+D механика

```python
page.keyboard.down('Shift')
page.keyboard.press('KeyD')
page.keyboard.up('Shift')
```

- Выбранные элементы отправляются в ZIP Google Takeout-like
- Playwright перехватывает скачивание через `page.expect_download()`

### Таймаут 120 секунд

```python
with page.expect_download(timeout=120000) as download_info:
    ...
download = download_info.value
```

⚠️ **Известная проблема:** иногда download не начинается → таймаут. См. [[known-issues]].

## Удаление

### JS evaluate для выбора и удаления

```python
page.evaluate('''
    const checkboxes = document.querySelectorAll('[role="checkbox"][aria-label]');
    for (const cb of checkboxes) {
        if (cb.getAttribute('aria-label').includes('Искомая дата')) {
            cb.click();
        }
    }
''')
# Затем: клик по кнопке корзины в toolbar
```

### Почему JS, не Playwright click

- Toolbar Google Photos динамически появляется/исчезает
- Playwright `wait_for_selector` иногда не успевает
- JS evaluate работает напрямую с актуальным DOM

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
