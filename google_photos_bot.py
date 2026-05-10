import os
import re
import shutil
import zipfile
import logging
import json
import hashlib
import time
from datetime import datetime, timedelta
from PIL import Image, ExifTags
from playwright.sync_api import sync_playwright

# --- НАСТРОЙКИ ПУТЕЙ И КОНФИГ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "DEST_DIR": "D:\\",
    "PROFILE_DIR": "bot_profile",
    "TEMP_DIR": "temp_zip",
    "STATE_FILE": "backup_manifest.json",
    "DAYS_TO_KEEP_IN_CLOUD": 180,
    "STOP_AT_DATE": "",
    "HEADLESS_MODE": False,
    "ALLOW_CLOUD_DELETE": True,
    "DRY_RUN_DELETE": True,
    "MAX_DELETE_BLOCKS_PER_RUN": 1,
    "LOG_LEVEL": "WARNING",
    "SCROLL_STEP_PIXELS": 500,
    "SCROLL_WAIT_MS": 1500
}

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
    config = DEFAULT_CONFIG
else:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

DEST_DIR = config.get("DEST_DIR", "D:\\")
PROFILE_DIR = config.get("PROFILE_DIR", "bot_profile")
if not os.path.isabs(PROFILE_DIR): PROFILE_DIR = os.path.join(BASE_DIR, PROFILE_DIR)
TEMP_DIR = config.get("TEMP_DIR", "temp_zip")
if not os.path.isabs(TEMP_DIR): TEMP_DIR = os.path.join(BASE_DIR, TEMP_DIR)
STATE_FILE = config.get("STATE_FILE", "backup_manifest.json")
if not os.path.isabs(STATE_FILE): STATE_FILE = os.path.join(BASE_DIR, STATE_FILE)

DAYS_TO_KEEP = config.get("DAYS_TO_KEEP_IN_CLOUD", 180)
HEADLESS_MODE = config.get("HEADLESS_MODE", False)
ALLOW_CLOUD_DELETE = config.get("ALLOW_CLOUD_DELETE", True)
DRY_RUN_DELETE = config.get("DRY_RUN_DELETE", False)
MAX_DELETE_BLOCKS_PER_RUN = config.get("MAX_DELETE_BLOCKS_PER_RUN", 0)
LOG_LEVEL_NAME = str(config.get("LOG_LEVEL", "WARNING")).upper()

def get_int_config(name, default, minimum):
    try:
        return max(minimum, int(config.get(name, default)))
    except (TypeError, ValueError):
        return default

SCROLL_STEP_PIXELS = get_int_config("SCROLL_STEP_PIXELS", 500, 100)
SCROLL_WAIT_MS = get_int_config("SCROLL_WAIT_MS", 1500, 500)
RUN_LEVEL = 25
logging.addLevelName(RUN_LEVEL, "RUN")
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": RUN_LEVEL,
}
LOG_LEVEL = LOG_LEVELS.get(LOG_LEVEL_NAME, RUN_LEVEL)

def parse_date(date_str):
    if date_str:
        try: return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError: pass
    return None

STOP_AT = parse_date(config.get("STOP_AT_DATE"))

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "app.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def log_run(message):
    logging.log(RUN_LEVEL, message)

def log_info(message):
    logging.info(message)

def log_debug(message):
    logging.debug(message)

# Создаем временную папку, если ее нет
os.makedirs(TEMP_DIR, exist_ok=True)

def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()

def normalize_label(label):
    return re.sub(r"\s+", " ", (label or "").replace("\u00a0", " ").replace("\u202f", " ")).strip()

def get_block_id(photo_date, aria_label):
    date_part = photo_date.strftime("%Y-%m-%d") if photo_date else "unknown"
    raw_id = f"{date_part}|{normalize_label(aria_label)}"
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:20]

def get_date_key(photo_date):
    return photo_date.strftime("%Y-%m-%d") if photo_date else None

def get_block_type(aria_label):
    label = normalize_label(aria_label).lower()
    if "выбрать все" in label or ("все фото" in label and "или позже" in label):
        return "group"
    if label.startswith("фотография") or label.startswith("видео"):
        return "item"
    return "block"

def load_manifest():
    if not os.path.exists(STATE_FILE):
        return {"version": 1, "blocks": {}, "covered_dates": {}}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        logging.error(f"❌ Не удалось прочитать manifest: {e}")
        return {"version": 1, "blocks": {}, "covered_dates": {}}

    if not isinstance(manifest, dict):
        return {"version": 1, "blocks": {}, "covered_dates": {}}
    manifest.setdefault("version", 1)
    manifest.setdefault("blocks", {})
    manifest.setdefault("covered_dates", {})
    return manifest

def save_manifest(manifest, attempts=8, retry_delay=0.15):
    tmp_path = f"{STATE_FILE}.tmp.{os.getpid()}"
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, STATE_FILE)
            return True
        except OSError as e:
            last_error = e
            winerror = getattr(e, "winerror", None)
            if winerror in (5, 32) and attempt < attempts:
                time.sleep(retry_delay * attempt)
                continue
            break
        except Exception as e:
            last_error = e
            break

    logging.error(f"❌ Не удалось сохранить manifest после {attempts} попыток: {last_error}")
    return False

def get_manifest_block(manifest, block_id, aria_label, photo_date):
    blocks = manifest.setdefault("blocks", {})
    entry = blocks.setdefault(block_id, {})
    entry.setdefault("id", block_id)
    entry["label"] = aria_label
    entry["normalized_label"] = normalize_label(aria_label)
    entry["photo_date"] = photo_date.strftime("%Y-%m-%d") if photo_date else None
    entry["last_seen_at"] = now_iso()
    entry.setdefault("first_seen_at", entry["last_seen_at"])
    entry.setdefault("files_verified", False)
    entry.setdefault("deleted_from_cloud", False)
    entry.setdefault("files", [])
    return entry

def mark_block_verified(manifest, block_id, file_stats):
    entry = manifest["blocks"][block_id]
    entry["files_verified"] = True
    entry["verified_at"] = now_iso()
    entry["download_stats"] = {
        "processed": file_stats.get("processed", 0),
        "new": file_stats.get("new", 0),
        "size": file_stats.get("size", 0)
    }
    entry["files"] = file_stats.get("files", [])
    entry["last_error"] = ""
    save_manifest(manifest)

def mark_date_covered(manifest, photo_date, block_id, file_stats):
    date_key = get_date_key(photo_date)
    if not date_key:
        return
    manifest.setdefault("covered_dates", {})[date_key] = {
        "date": date_key,
        "covering_block_id": block_id,
        "files_verified": True,
        "files_count": file_stats.get("processed", 0),
        "verified_at": now_iso()
    }
    save_manifest(manifest)

def get_verified_date_coverage(manifest, photo_date):
    date_key = get_date_key(photo_date)
    if not date_key:
        return None

    coverage = manifest.setdefault("covered_dates", {}).get(date_key)
    if not coverage or not coverage.get("files_verified"):
        return None

    covering_block = manifest.setdefault("blocks", {}).get(coverage.get("covering_block_id"), {})
    if not covering_block.get("files_verified"):
        return None
    return coverage

def mark_block_covered_by(manifest, block_id, coverage):
    entry = manifest["blocks"][block_id]
    entry["files_verified"] = True
    entry["verification_source"] = "date_coverage"
    entry["covered_by_block_id"] = coverage.get("covering_block_id")
    entry["covered_at"] = now_iso()
    entry["last_error"] = ""
    save_manifest(manifest)

def rebuild_date_coverage_from_blocks(manifest):
    changed = False
    covered_dates = manifest.setdefault("covered_dates", {})

    for block_id, entry in manifest.setdefault("blocks", {}).items():
        if not entry.get("files_verified"):
            continue
        if entry.get("block_type") != "group" and get_block_type(entry.get("label", "")) != "group":
            continue

        date_key = entry.get("photo_date")
        if not date_key:
            continue

        current = covered_dates.get(date_key)
        current_count = current.get("files_count", 0) if current else 0
        files_count = len(entry.get("files") or [])
        if not current or files_count > current_count:
            covered_dates[date_key] = {
                "date": date_key,
                "covering_block_id": block_id,
                "files_verified": True,
                "files_count": files_count,
                "verified_at": entry.get("verified_at", now_iso())
            }
            changed = True

    if changed:
        return save_manifest(manifest)
    return True

def mark_block_error(manifest, block_id, error_message):
    entry = manifest["blocks"][block_id]
    entry["last_error"] = error_message
    entry["last_error_at"] = now_iso()
    return save_manifest(manifest)

def mark_block_deleted(manifest, block_id):
    deleted_at = now_iso()
    blocks = manifest.setdefault("blocks", {})
    entry = manifest["blocks"][block_id]
    entry["deleted_from_cloud"] = True
    entry["deleted_at"] = deleted_at
    cascaded_count = 0
    for child_id, child_entry in blocks.items():
        if child_id == block_id:
            continue
        if child_entry.get("covered_by_block_id") != block_id:
            continue
        if child_entry.get("deleted_from_cloud"):
            continue
        child_entry["deleted_from_cloud"] = True
        child_entry["deleted_at"] = deleted_at
        child_entry["deleted_with_block_id"] = block_id
        cascaded_count += 1
    if not save_manifest(manifest):
        raise RuntimeError("Cloud delete succeeded, but manifest could not be saved")
    return cascaded_count

def wait_for_delete_completion(page, safe_label):
    block_selector = f'div[role="checkbox"][aria-label="{safe_label}"]'
    page.wait_for_selector('div[role="dialog"]:visible', state='hidden', timeout=15000)
    try:
        page.wait_for_selector(block_selector, state='detached', timeout=15000)
    except Exception as e:
        if page.locator(block_selector).count() > 0:
            raise RuntimeError("Google Photos did not remove the selected block after delete confirmation") from e

def get_verified_file_count(entry):
    files = entry.get("files") or []
    return len(files) if files else 1

def sha256_file(filepath):
    digest = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def safe_extract_zip(zip_ref, target_dir):
    target_dir_abs = os.path.abspath(target_dir)
    for member in zip_ref.infolist():
        target_path = os.path.abspath(os.path.join(target_dir_abs, member.filename))
        if not target_path.startswith(target_dir_abs + os.sep) and target_path != target_dir_abs:
            raise ValueError(f"Unsafe ZIP path: {member.filename}")
    zip_ref.extractall(target_dir_abs)

def format_size(size_bytes):
    """Форматирует байты в читаемый вид (КБ, МБ, ГБ)."""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} ПБ"

def get_days_old(aria_label):
    """Определяет возраст группы фотографий в днях и возвращает (дни, объект_даты)."""
    label = aria_label.lower()
    now = datetime.now()
    
    if 'сегодня' in label:
        return 0, now.replace(hour=0, minute=0, second=0, microsecond=0)
    if 'вчера' in label:
        return 1, (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
    # Ищем дату (например: "4 мая", "28 авг. 2023", "понедельник, 1 ноя")
    match = re.search(r'(\d{1,2})\s+([а-яa-z]+)\.?(?:\s+(\d{4}))?', label)
    if match:
        day = int(match.group(1))
        month_str = match.group(2)[:3]
        year = int(match.group(3)) if match.group(3) else now.year
        
        month = 1
        for k, v in {
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'мая': 5, 'май': 5,
            'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }.items():
            if month_str.startswith(k):
                month = v
                break
                
        try:
            photo_date = datetime(year, month, day)
            # Если год не указан, но месяц больше текущего (значит это фото прошлого года)
            if not match.group(3) and photo_date > now:
                photo_date = photo_date.replace(year=year - 1)
            return max(0, (now - photo_date).days), photo_date
        except ValueError:
            pass
            
    return 0, None # При ошибке парсинга лучше не удалять фото (перестраховка)

def get_year_from_file(filepath):
    """Попытка вытащить год создания из имени файла или EXIF-метаданных."""
    filename = os.path.basename(filepath)
    
    # 1. Ищем дату в имени файла (например, VID_20230501_123000.mp4 или Screenshot_2024-12-31)
    # Ищем год (20xx), затем месяц (01-12) и день (01-31), разделенные _, - или без них
    match = re.search(r'(20\d{2})[-_]?(?:0[1-9]|1[0-2])[-_]?(?:0[1-9]|[12]\d|3[01])', filename)
    if match:
        return match.group(1)

    # 2. Если в имени нет даты, пробуем EXIF (только для фото)
    try:
        with Image.open(filepath) as img:
            exif = img._getexif()
        if exif:
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                # Ищем тег даты оригинальной съемки
                if tag_name == 'DateTimeOriginal' and isinstance(value, str):
                    # Формат EXIF обычно: "2025:05:01 12:00:00"
                    year = value.split(":")[0]
                    if len(year) == 4 and year.isdigit():
                        return year
    except Exception:
        pass
    return None

def process_downloaded_file(download_path, ui_fallback_year):
    """Обрабатывает скачанный файл (ZIP-архив или одиночный медиафайл), сортирует и удаляет исходник."""
    extract_folder = os.path.join(TEMP_DIR, "extracted")
    
    # Очищаем папку распаковки, если она осталась после прошлой ошибки
    if os.path.exists(extract_folder):
        shutil.rmtree(extract_folder)
    os.makedirs(extract_folder, exist_ok=True)
    
    files_to_process = []
    is_zip = download_path.lower().endswith('.zip')
    
    if is_zip:
        log_debug("📦 Распаковка архива...")
        try:
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                safe_extract_zip(zip_ref, extract_folder)
            for root, dirs, files in os.walk(extract_folder):
                for file in files:
                    if not file.endswith(".json"):
                        files_to_process.append(os.path.join(root, file))
        except Exception as e:
            logging.error(f"❌ Ошибка распаковки архива: {e}")
            return {"success": False, "verified": False, "processed": 0, "new": 0, "size": 0, "files": []}
    else:
        log_debug("🖼️ Обработка одиночного медиафайла...")
        filename = os.path.basename(download_path)
        if not filename.endswith(".json"):
            temp_file_path = os.path.join(extract_folder, filename)
            shutil.move(download_path, temp_file_path)
            files_to_process.append(temp_file_path)

    files_processed = 0
    new_files = 0
    verified_files = 0
    total_size = 0
    file_records = []
    
    # Проходим по всем извлеченным файлам
    for file_path in files_to_process:
        file = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        total_size += file_size
        file_hash = sha256_file(file_path)
            
        # Логика определения года: 1. Имя файла / EXIF, 2. Текст из UI, 3. Текущий год
        year = get_year_from_file(file_path)
        if not year:
            year = ui_fallback_year
        
        # Формируем целевую папку на основе конфига
        dest_folder = os.path.join(DEST_DIR, f"Фото Google {year}")
        os.makedirs(dest_folder, exist_ok=True)
        
        dest_file_path = os.path.join(dest_folder, file)
        
        # Проверка на наличие файла от прерванного запуска
        file_is_already_saved = False
        if os.path.exists(dest_file_path):
            # Если размеры совпадают, значит файл уже был успешно сохранен ранее
            if sha256_file(dest_file_path) == file_hash:
                file_is_already_saved = True
            else:
                # Размеры разные (например, другой файл с таким же именем). Ищем новое имя.
                counter = 1
                name, ext = os.path.splitext(file)
                while os.path.exists(dest_file_path):
                    if sha256_file(dest_file_path) == file_hash:
                        file_is_already_saved = True
                        break
                    dest_file_path = os.path.join(dest_folder, f"{name}_{counter}{ext}")
                    counter += 1
        
        if file_is_already_saved:
            # Удаляем временный файл, так как его копия уже есть на D:\
            os.remove(file_path)
        else:
            shutil.move(file_path, dest_file_path)
            new_files += 1

        if os.path.exists(dest_file_path) and sha256_file(dest_file_path) == file_hash:
            verified_files += 1
        file_records.append({
            "name": file,
            "path": dest_file_path,
            "year": str(year),
            "size": file_size,
            "sha256": file_hash,
            "already_saved": file_is_already_saved
        })
            
        files_processed += 1

    # Очищаем временные файлы
    shutil.rmtree(extract_folder)
    if os.path.exists(download_path):
        os.remove(download_path)
        
    log_info(f"✅ Успешно обработано {files_processed} файлов.")
    return {
        "success": files_processed > 0,
        "verified": files_processed > 0 and verified_files == files_processed,
        "processed": files_processed,
        "new": new_files,
        "size": total_size,
        "files": file_records
    }

def main():
    with sync_playwright() as p:
        log_run("🌐 Запуск Google Photos backup bot")
        # Запускаем браузер с сохранением сессии (куки, логин)
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=HEADLESS_MODE, # Читаем из конфига
            viewport={"width": 1920, "height": 1080}, # Фиксируем Full HD разрешение для надежной работы React
            accept_downloads=True,
            channel="chrome", # Использовать стандартный движок (помогает от банов)
            args=["--disable-blink-features=AutomationControlled", "--window-size=1920,1080"],
            ignore_default_args=["--enable-automation"]
        )
        
        page = browser.new_page()
        page.goto("https://photos.google.com/")
        
        # Ждем немного, чтобы браузер успел сделать редирект, если сессии нет
        page.wait_for_timeout(2000)
        
        if "accounts.google.com" in page.url or "signin" in page.url:
            log_debug("⏳ Требуется авторизация... (Авторизуйтесь, у вас есть 5 минут)")
            page.wait_for_url("https://photos.google.com/**", timeout=300000)
            log_debug("✅ Авторизация пройдена!")
            page.wait_for_timeout(3000) # Даем интерфейсу загрузиться
            
        log_debug("🔍 Поиск фотографий в галерее...")
        try:
            # Ждем появления чекбоксов. state='attached' найдет их, даже если они визуально скрыты без наведения
            page.wait_for_selector('div[role="checkbox"][aria-label]:not([aria-checked="true"])', state='attached', timeout=15000)
            log_debug("✅ Галерея загружена, начинаем работу.")
        except Exception:
            log_run("🏁 Фотографии не найдены. Галерея пуста либо скрипт дошел до конца. Завершаем работу.")
            browser.close()
            return
        
        # Основной цикл обработки блоков (групп фото по датам)
        processed_labels = set()
        processed_block_ids = set()
        scroll_attempts = 0
        
        # Статистика сессии
        stats = {
            "new_downloaded": 0,
            "total_deleted": 0,
            "total_bytes": 0,
            "downloaded_dates": [],
            "deleted_dates": []
        }
        manifest = load_manifest()
        rebuild_date_coverage_from_blocks(manifest)
        delete_blocks_this_run = 0
        delete_limit_reached = False
        
        while True:
            try:
                # Явно дожидаемся появления хотя бы одной невыделенной галочки
                # Таймаут 15 секунд для перехода между группами
                page.wait_for_selector('div[role="checkbox"][aria-label]:not([aria-checked="true"])', state='attached', timeout=15000)
            except Exception:
                log_debug("🏁 Больше не найдено групп фотографий (или истекло время ожидания). Скрипт завершает работу.")
                break

            # Находим галочки, которые мы еще не обрабатывали в этом сеансе
            checkboxes = page.locator('div[role="checkbox"][aria-label]:not([aria-checked="true"])').all()
            group_checkbox = None
            
            should_stop_script = False
            for cb in checkboxes:
                try:
                    label = cb.get_attribute("aria-label") or ""
                    if label and label not in processed_labels:
                        # Убеждаемся, что это именно фото или группа (можно спарсить дату)
                        days_old, photo_date = get_days_old(label)
                        if photo_date is not None:
                            
                            # 1. Проверка на остановку (если дошли до старых фото)
                            if STOP_AT and photo_date <= STOP_AT:
                                should_stop_script = True
                                break

                            candidate_block_id = get_block_id(photo_date, label)
                            if candidate_block_id in processed_block_ids:
                                processed_labels.add(label)
                                continue
                                
                            group_checkbox = cb
                            break
                except Exception:
                    continue
                    
            if should_stop_script:
                log_run(f"🛑 Достигнута дата остановки ({config.get('STOP_AT_DATE')}). Завершаем работу.")
                break
                
            if not group_checkbox:
                if scroll_attempts > 30:
                    log_debug("🏁 Достигнут конец галереи или зависла прокрутка. Завершаем работу.")
                    break
                log_debug("⏬ Все видимые фото обработаны. Плавная прокрутка вниз...")
                
                # Умная прокрутка: сперва докручиваем до последнего видимого чекбокса
                if checkboxes:
                    try:
                        checkboxes[-1].scroll_into_view_if_needed(timeout=1000)
                    except Exception:
                        pass
                        
                # Затем ставим мышь в центр экрана (чтобы скролл точно сработал) и крутим колесо
                page.locator('body').focus()
                page.mouse.move(960, 540) # Центр экрана 1920x1080
                page.mouse.wheel(0, SCROLL_STEP_PIXELS)
                page.wait_for_timeout(SCROLL_WAIT_MS)
                    
                scroll_attempts += 1
                continue
                
            scroll_attempts = 0 # Сбрасываем счетчик

            # Визуальный разделитель для удобства чтения логов
            log_debug("-" * 50)

            # 1. Считываем текст, чтобы понять возраст и год
            aria_label = group_checkbox.get_attribute("aria-label") or ""
            processed_labels.add(aria_label) # Запоминаем, чтобы не обрабатывать повторно
            
            days_old, photo_date = get_days_old(aria_label)
            should_delete = days_old > DAYS_TO_KEEP
            
            block_id = get_block_id(photo_date, aria_label)
            processed_block_ids.add(block_id)
            manifest_entry = get_manifest_block(manifest, block_id, aria_label, photo_date)
            block_type = get_block_type(aria_label)
            manifest_entry["block_type"] = block_type
            block_verified = bool(manifest_entry.get("files_verified"))
            date_coverage = get_verified_date_coverage(manifest, photo_date) if block_type != "group" else None
            if date_coverage and not block_verified:
                mark_block_covered_by(manifest, block_id, date_coverage)
                manifest_entry = manifest["blocks"][block_id]
                block_verified = True
            should_download = not block_verified
                
            status_msg = "УДАЛЯЕМ" if should_delete else "ОСТАВЛЯЕМ В ОБЛАКЕ"
            action_msg = "СКАЧИВАЕМ" if should_download else "ПРОПУСКАЕМ СКАЧИВАНИЕ"
            
            log_debug(f"🎯 Найдена группа: {aria_label} (Возраст: {days_old} дн. -> {action_msg}, {status_msg})")

            if block_verified and not should_delete:
                log_debug("⏩ Блок уже подтвержден manifest и остается в облаке. UI-выделение не требуется.")
                continue

            if block_verified and should_delete and (DRY_RUN_DELETE or not ALLOW_CLOUD_DELETE):
                log_info("🧪 Блок старше порога и уже подтвержден manifest. Dry-run: был бы удален из облака.")
                continue

            if block_verified and should_delete and MAX_DELETE_BLOCKS_PER_RUN and delete_blocks_this_run >= MAX_DELETE_BLOCKS_PER_RUN:
                if not delete_limit_reached:
                    logging.warning("⚠️ Достигнут лимит MAX_DELETE_BLOCKS_PER_RUN. Дальнейшие кандидаты на удаление будут пропущены без UI-выделения.")
                    delete_limit_reached = True
                continue

            match = re.search(r'(20\d{2})', aria_label)
            ui_year = match.group(1) if match else str(datetime.now().year)

            # Принудительно возвращаем фокус на страницу перед выделением
            page.bring_to_front()
            page.locator('body').focus()
    
            # 2. Выделяем блок (Используем СТАТИЧНЫЙ локатор, не зависящий от состояния checked)
            safe_label = aria_label.replace('"', '\\"') # Экранируем возможные кавычки
            static_cb = page.locator(f'div[role="checkbox"][aria-label="{safe_label}"]').first
            
            is_checked = False
            
            # Обязательно скроллим к элементу, чтобы React Virtual DOM отрендерил его
            try:
                static_cb.scroll_into_view_if_needed(timeout=2000)
                page.wait_for_timeout(500)
            except Exception:
                pass
            
            for attempt in range(3):
                try:
                    # Кликаем по статичному локатору (force=True пробивает плавающие панели)
                    static_cb.click(force=True, timeout=3000)
                    
                    # Ждем, пока именно этот элемент получит статус aria-checked="true"
                    page.wait_for_selector(f'div[role="checkbox"][aria-label="{safe_label}"][aria-checked="true"]', state='attached', timeout=3000)
                    is_checked = True
                    break
                except Exception as e:
                    # В случае ошибки интерфейса, пробуем запасной JS-клик
                    try:
                        static_cb.evaluate("el => el.click()")
                        page.wait_for_timeout(1000)
                        if static_cb.get_attribute("aria-checked") == "true":
                            is_checked = True
                            break
                    except Exception as inner_e:
                        if attempt == 2: # Логируем только если все 3 попытки (включая JS) провалились
                            logging.warning("⚠️ Все попытки клика (включая JS) не удались.")
                        
                    page.wait_for_timeout(1000)
                
            if not is_checked:
                logging.error("❌ Не удалось выделить фото (галочка не поставилась после 3 попыток). Скрипт остановлен.")
                break
                    
            page.wait_for_timeout(500) # Короткая пауза для анимации перед скачиванием
            
            success = False
            zip_stats = {"processed": 0, "size": 0, "new": 0, "success": False, "verified": False, "files": []}
            
            if should_download:
                # 3. Скачиваем (эмуляция Shift+D)
                log_debug("⬇️ Запрашиваем скачивание (архива или файла)...")
                try:
                    with page.expect_download(timeout=120000) as download_info:
                        page.keyboard.press("Shift+D")
                        download = download_info.value
                        
                        download_path = os.path.join(TEMP_DIR, download.suggested_filename)
                        download.save_as(download_path)
                        log_info(f"📥 Скачан файл: {download.suggested_filename}")
                        
                        # 4. Обрабатываем и сортируем на D:\
                        zip_stats = process_downloaded_file(download_path, ui_year)
                        success = zip_stats["success"]
                        
                        if success:
                            if not zip_stats.get("verified"):
                                mark_block_error(manifest, block_id, "Downloaded files were not fully verified on disk")
                                logging.warning("⚠️ Файлы скачаны, но локальная проверка hash не подтверждена. Удаление запрещено.")
                                break
                            mark_block_verified(manifest, block_id, zip_stats)
                            if block_type == "group":
                                mark_date_covered(manifest, photo_date, block_id, zip_stats)
                            block_verified = True
                            manifest_entry = manifest["blocks"][block_id]
                            batch_size_str = format_size(zip_stats["size"])
                            log_info(f"📊 Порция: {zip_stats['processed']} файлов (новых: {zip_stats['new']}), объем: {batch_size_str}")
                            
                            stats["total_bytes"] += zip_stats["size"]
                            stats["new_downloaded"] += zip_stats["new"]
                            if zip_stats["new"] > 0 and photo_date:
                                stats["downloaded_dates"].append(photo_date)
                        else:
                            logging.warning("⚠️ Архив оказался пуст или произошла ошибка. Пропускаем удаление.")
                            break # Останавливаем скрипт от греха подальше
                            
                except Exception as e:
                    logging.error(f"❌ Ошибка при скачивании блока: {e}")
                    log_run("Скрипт остановлен для безопасности.")
                    break
            else:
                log_debug("⏩ Блок уже подтвержден в manifest. Пропускаем скачивание.")
                zip_stats["processed"] = get_verified_file_count(manifest_entry)
                zip_stats["verified"] = True
                zip_stats["files"] = manifest_entry.get("files", [])
                success = True
                
            if success:
                try:
                    if should_delete:
                        if not block_verified:
                            logging.warning("⚠️ Блок старше DAYS_TO_KEEP_IN_CLOUD, но локальный архив не подтвержден. Удаление запрещено.")
                            mark_block_error(manifest, block_id, "Cloud delete blocked: archive is not verified")
                            page.keyboard.press("Escape")
                            try:
                                page.wait_for_selector('button[aria-label="Удалить"], button[aria-label="В корзину"]', state='hidden', timeout=3000)
                            except Exception:
                                pass
                            page.wait_for_timeout(1000)
                            continue

                        if not ALLOW_CLOUD_DELETE or DRY_RUN_DELETE:
                            log_info("🧪 Удаление из облака отключено настройками. Блок оставлен в Google Photos.")
                            page.keyboard.press("Escape")
                            try:
                                page.wait_for_selector('button[aria-label="Удалить"], button[aria-label="В корзину"]', state='hidden', timeout=3000)
                            except Exception:
                                pass
                            page.wait_for_timeout(1000)
                            continue

                        # Проверяем, не снял ли Google выделение после скачивания (это происходит автоматически)
                        if should_download:
                            page.wait_for_timeout(1000)
                            if static_cb.get_attribute("aria-checked") != "true":
                                log_debug("🔄 Восстанавливаем выделение перед удалением (Google сбросил его)...")
                                page.bring_to_front()
                                page.locator('body').focus()
                                try:
                                    static_cb.scroll_into_view_if_needed(timeout=2000)
                                    page.wait_for_timeout(500)
                                    static_cb.click(force=True, timeout=3000)
                                except Exception:
                                    static_cb.evaluate("el => el.click()")
                                page.wait_for_selector(f'div[role="checkbox"][aria-label="{safe_label}"][aria-checked="true"]', state='attached', timeout=5000)

                        # 5. УДАЛЕНИЕ (только если скачивание успешно или пропущено, и возраст > DAYS_TO_KEEP_IN_CLOUD)
                        log_info("🗑️ Удаляем фото из облака...")
                        # Кнопка корзины вверху справа
                        page.locator('button[aria-label="Удалить"]:visible, button[aria-label="В корзину"]:visible').first.click()
                        
                        # Подтверждение в модальном окне
                        page.wait_for_timeout(1000)
                        confirm_button = page.locator('div[role="dialog"] button:has-text("В корзину"):visible, div[role="dialog"] button:has-text("Удалить"):visible').last
                        confirm_button.wait_for(timeout=10000)
                        confirm_button.click()
                        wait_for_delete_completion(page, safe_label)
                        
                        log_info("✅ Блок обработан и удален.")
                        stats["total_deleted"] += zip_stats["processed"] if should_download else get_verified_file_count(manifest_entry)
                        delete_blocks_this_run += 1
                        cascaded_deleted = mark_block_deleted(manifest, block_id)
                        if cascaded_deleted:
                            log_info(f"✅ В manifest каскадно отмечено дочерних item-записей: {cascaded_deleted}")
                        if photo_date:
                            stats["deleted_dates"].append(photo_date)
                    else:
                        page.keyboard.press("Escape") # Сбрасываем выделение с этих фото
                        try:
                            page.wait_for_selector('button[aria-label="Удалить"], button[aria-label="В корзину"]', state='hidden', timeout=3000)
                        except Exception:
                            pass
                        log_debug("✅ Выделение снято, переходим к следующему блоку.")
                        
                    page.wait_for_timeout(2000) # Пауза перед переходом к следующей группе
                except Exception as e:
                    logging.error(f"❌ Ошибка при удалении/снятии выделения: {e}")
                    log_run("Скрипт остановлен для безопасности.")
                    break

        # ИТОГОВЫЙ ОТЧЕТ
        log_run("========================================")
        log_run("🏁 ИТОГОВЫЙ ОТЧЕТ О РАБОТЕ СКРИПТА")
        log_run("========================================")
        log_run(f"💾 Общий объем обработанных медиафайлов: {format_size(stats['total_bytes'])}")
        log_run(f"📥 Новых файлов скачано: {stats['new_downloaded']}")
        if stats['downloaded_dates']:
            min_d = min(stats['downloaded_dates']).strftime('%d.%m.%Y')
            max_d = max(stats['downloaded_dates']).strftime('%d.%m.%Y')
            log_run(f"📅 Период новых скачанных файлов: с {min_d} по {max_d}")
            
        log_run(f"🗑️ Файлов удалено из облака: {stats['total_deleted']}")
        if stats['deleted_dates']:
            min_del = min(stats['deleted_dates']).strftime('%d.%m.%Y')
            max_del = max(stats['deleted_dates']).strftime('%d.%m.%Y')
            log_run(f"📅 Период удаленных файлов: с {min_del} по {max_del}")
        log_run("========================================")

        browser.close()

if __name__ == "__main__":
    main()
