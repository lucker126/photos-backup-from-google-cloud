# Установка и первый запуск

## Требования

- Windows 10/11
- Python 3.10+
- Google-аккаунт с Google Photos
- ~10+ GB свободного места на целевом диске

## Быстрый старт

```bat
git clone https://github.com/lucker126/photos-backup-from-google-cloud.git
cd photos-backup-from-google-cloud
start_bot.bat
```

`start_bot.bat` выполняет:
1. `python -m venv venv` (если нет)
2. `venv\Scripts\activate.bat`
3. `pip install -r requirements.txt`
4. `playwright install chromium`
5. `python google_photos_bot.py`

## Авторизация и повторный вход

### Первый запуск

1. Откроется Chrome с photos.google.com
2. Бот до 10 сек определяет состояние: видна галерея или форма логина Google
3. Если обнаружена форма логина — введите email/пароль вручную, бот ждет до `AUTH_WAIT_TIMEOUT_MS` (по умолчанию 5 минут)
4. Подтвердите 2FA если требуется
5. После входа (и успешного рендера галереи) бот продолжит автоматически

### Повторный запуск с истекшей сессией

Сессия хранится в профиле `bot_profile` (cookies). Если с момента прошлого запуска сессия истекла:

- Бот детектирует форму логина за ~10 секунд (polling состояния страницы, без фиксированных таймаутов)
- Ждет ручного входа/2FA до `AUTH_WAIT_TIMEOUT_MS` мс (default 300000 = 5 мин, настраивается в `config.json`)
- После входа продолжает работу с того же места — повторных действий не требуется

При валидной сессии лишних ожиданий нет: галерея детектируется в пределах пары секунд, и бот сразу начинает работу.

### Если Google разлогинил посреди работы

Тот же механизм срабатывает и внутри основного цикла: при исчезновении галереи бот проверяет, не произошел ли редирект на логин, и при необходимости снова дает `AUTH_WAIT_TIMEOUT_MS` на ручной вход, после чего продолжает обработку (а не завершается с ложным «галерея пуста»).

### «Залипший» профиль (fallback)

Если страница логина детектируется, но войти не получается (капча, подвисшая сессия), остановите бота, удалите или переименуйте папку `bot_profile` и запустите заново — будет чистый профиль с полной формой входа.

## Проверка первого запуска (безопасная конфигурация)

`config.json` после первого запуска:
```json
{
  "DRY_RUN_DELETE": true,
  "ALLOW_CLOUD_DELETE": false,
  "HEADLESS_MODE": false,
  "MAX_DELETE_BLOCKS_PER_RUN": 0
}
```

С этими настройками бот:
- Скачает файлы
- Проверит хеши
- Запишет в manifest
- **Ничего не удалит** из облака

## Проверка результата

```bat
python manifest_report.py
```

Ожидаемый вывод: сводка по скачанным блокам, файлам, годам.

## Ручная установка (без .bat)

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install playwright==1.59.0 Pillow==12.2.0
playwright install chromium
python google_photos_bot.py
```

## Структура после установки

```
photos-backup/
├── venv/                    # виртуальное окружение
├── bot_profile/             # профиль Chrome (cookies)
├── temp_zip/                # временные ZIP
├── backup_manifest.json     # состояние
├── app.log                  # логи
├── config.json              # настройки
└── D:\Фото Google YYYY\     # ваши фото (на целевом диске)
```

## Обновление

```bash
git pull
venv\Scripts\activate
pip install -r requirements.txt  # если изменились зависимости
playwright install chromium       # если обновилась версия
```

Manifest (`backup_manifest.json`) мигрируется автоматически при запуске.
