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

## Первая авторизация

1. Откроется Chrome с photos.google.com
2. Если не авторизован — появится страница входа Google
3. Введите email/пароль вручную (бот ждет до 5 минут)
4. Подтвердите 2FA если требуется
5. После входа бот продолжит автоматически

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
