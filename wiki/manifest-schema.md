# Схема `backup_manifest.json`

## Структура верхнего уровня

```json
{
  "version": 3,
  "items": {
    "<block_id>": { ...entry... }
  }
}
```

- `version` — целое, текущая версия схемы. При загрузке выполняется миграция legacy (v1/v2 → v3).
- `items` — словарь: ключ = `block_id`, значение = запись блока.

## block_id

Идентификатор блока. Два формата:
- `"GROUP: <текст заголовка>"` — группа фото по дню (например `GROUP: 15 июля 2023 г.`)
- `"ITEM: <текст элемента>"` — одиночный медиа-файл (например `ITEM: IMG_20230715_143022.jpg`)

## Запись (entry)

| Поле | Тип | Описание |
|------|-----|----------|
| `block_id` | string | Дублирует ключ (для self-contained записей) |
| `block_type` | string | `"group"` или `"item"` |
| `block_text` | string | Оригинальный текст из UI |
| `date` | string | ISO дата блока `YYYY-MM-DD` (из aria-label) |
| `download_date` | string | ISO datetime скачивания |
| `files` | array | Список файлов блока (см. ниже) |
| `files_verified` | bool | `true` только если ВСЕ файлы подтверждены SHA-256 на диске |
| `deleted_from_cloud` | bool | `true` если блок удален из облака |
| `deleted_date` | string? | ISO datetime удаления (если было) |
| `partial` | bool? | `true` если при распаковке часть файлов не прошла верификацию |
| `count` | int? | Ожидаемое число файлов из метаданных (`"Фото · N элементов"`) |

### Объект файла (элемент `files`)

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | string | Имя файла |
| `path` | string | Абсолютный путь на диске |
| `sha256` | string | Хеш содержимого |
| `size` | int | Размер в байтах |
| `year` | int? | Год из EXIF/имени (для распределения по папкам) |

## Пример

```json
{
  "version": 3,
  "items": {
    "GROUP: 15 июля 2023 г.": {
      "block_id": "GROUP: 15 июля 2023 г.",
      "block_type": "group",
      "date": "2023-07-15",
      "download_date": "2026-07-30T22:14:03",
      "files_verified": true,
      "deleted_from_cloud": true,
      "deleted_date": "2026-07-30T22:15:41",
      "files": [
        {
          "name": "IMG_20230715_143022.jpg",
          "path": "D:\\Фото Google 2023\\IMG_20230715_143022.jpg",
          "sha256": "a1b2...",
          "size": 3145728,
          "year": 2023
        }
      ]
    }
  }
}
```

## Жизненный цикл записи

1. **Создание** — после успешной распаковки + верификации → `files_verified=true`
2. **Partial** — если часть файлов не сошлась по хешу → `partial=true`, `files_verified=false`
3. **Удаление** — после удаления из облака → `deleted_from_cloud=true`

## Инварианты

- Запись с `files_verified=false` **никогда** не удаляется из облака.
- `deleted_from_cloud=true` только при `files_verified=true`.
- При перезапуске блок с `files_verified=true` и `deleted_from_cloud=false` — кандидат на удаление (если прошел `DAYS_TO_KEEP_IN_CLOUD`).

## Legacy-миграция

`load_manifest()` автоматически:
- Конвертирует старые ключи (`blocks` → `items`)
- Удаляет дубликаты по `block_id`
- Дополняет недостающие поля дефолтами
- Записывает `version=3`

## Date coverage

"Покрытие" — одиночные `ITEM:` записи на ту же дату, что и `GROUP:`, считаются покрытыми группой после её верификации. Это позволяет избежать повторного скачивания отдельных фото. Функция покрытия реализована в `run()` и отражается в отчётах `manifest_report.py --orphans`.
