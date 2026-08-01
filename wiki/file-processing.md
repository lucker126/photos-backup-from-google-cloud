# Обработка файлов

Путь файла от скачанного ZIP до верифицированной копии на диске.

## Поток

```
Google Photos → Shift+D → ZIP → TEMP_DIR → extract → dedup → DEST_DIR/Фото Google YYYY/ → SHA-256 → manifest
```

## Распаковка

```python
with zipfile.ZipFile(zip_path, 'r') as z:
    z.extractall(TEMP_DIR)
```

Google Photos отдает ZIP с плоской структурой или подпапкой `Takeout/Google Photos/Photo from YYYY/`.

## Определение года

`correct_file_date(file_path)` — двухэтапное определение:

1. **EXIF** (Pillow): `Image.open(path)._getexif()` → тег 36867 (`DateTimeOriginal`) или 306 (`DateTime`)
2. **Fallback — имя файла**: паттерны:
   - `IMG_YYYYMMDD_*.jpg`
   - `VID_YYYYMMDD_*.mp4`
   - `YYYY-MM-DD_*`
   - `Screenshot_YYYYMMDD-*`
   - RU/EN варианты дат в имени

Если год не определен — используется год блока из `date` в manifest.

## Дедупликация

### Внутри блока
Если два файла в одном ZIP имеют одинаковое имя → пропуск дубликата (первый выигрывает).

### Между годами (cross-year dedup)
Перед копированием в `Фото Google YYYY/` проверяется: есть ли файл с тем же `sha256` в других папках годов? Если есть — файл не копируется, в manifest записывается существующий путь.

```python
if hash_exists_in_other_years(sha256, current_year):
    use_existing_path()
```

## Структура целевых папок

```
DEST_DIR/
├── Фото Google 2019/
├── Фото Google 2020/
├── Фото Google 2023/
└── ...
```

Файлы внутри года — плоские (без подпапок по месяцам/дням).

## Config JSON в ZIP

Google иногда кладет `metadata.json` или `*-мэтADATA.json` в ZIP. Эти файлы:
- Не копируются в DEST_DIR
- Используются только для извлечения метаданных, если реализовано (`_try_set_avhd_keys`)

## Обработка ошибок распаковки

| Ошибка | Действие |
|--------|----------|
| Corrupt ZIP | Лог ERROR, блок пропускается, manifest не обновляется |
| Нет файлов в ZIP | `files=[]`, `files_verified=false` |
| Часть файлов битые | `partial=true`, verified=false, ошибочные файлы в логе |

## Очистка TEMP_DIR

После успешной обработки ZIP удаляется. Оставшиеся файлы при сбое — признак проблемы, чистятся вручную или при следующем запуске.

## Производительность

- SHA-256 ~500 MB/s на SSD
- Распаковка ZIP ~ограничена CPU (zipfile на Python)
- Bottleneck — скачивание (Google Photos rate limit), а не локальная обработка
