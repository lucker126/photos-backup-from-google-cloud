"""Configuration manager for Google Photos Backup & Sync Bot.

Handles loading, validating, and saving config.json.
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

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
    "SCROLL_WAIT_MS": 1500,
    "AUTH_WAIT_TIMEOUT_MS": 300000,
    "DOWNLOAD_TIMEOUT_MS": 120000,
    "DOWNLOAD_MAX_RETRIES": 3,
}


def load_config(path: str = None) -> dict:
    """Loads configuration from JSON file, merging with default values."""
    target_path = path or CONFIG_PATH
    config = DEFAULT_CONFIG.copy()

    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    config.update(loaded)
        except Exception:
            pass
    return config


def validate_config(data: dict) -> tuple[bool, str | None]:
    """Validates configuration values. Returns (True, None) or (False, error_message)."""
    if not isinstance(data, dict):
        return False, "Конфигурация должна быть объектом (словарем)."

    dest_dir = data.get("DEST_DIR")
    if not dest_dir or not isinstance(dest_dir, str) or not dest_dir.strip():
        return False, "Папка сохранения (DEST_DIR) не может быть пустой."

    # Validate DAYS_TO_KEEP_IN_CLOUD
    try:
        days = int(data.get("DAYS_TO_KEEP_IN_CLOUD", 180))
        if days < 0:
            return False, "Количество дней хранения в облаке должно быть >= 0."
    except (ValueError, TypeError):
        return False, "Количество дней хранения должно быть целым числом."

    # Validate STOP_AT_DATE
    stop_date = data.get("STOP_AT_DATE", "")
    if stop_date and isinstance(stop_date, str) and stop_date.strip():
        try:
            datetime.strptime(stop_date.strip(), "%Y-%m-%d")
        except ValueError:
            return False, "Дата остановки должна быть в формате ГГГГ-ММ-ДД (например, 2024-01-01)."

    # Validate MAX_DELETE_BLOCKS_PER_RUN
    try:
        max_del = int(data.get("MAX_DELETE_BLOCKS_PER_RUN", 0))
        if max_del < 0:
            return False, "Лимит удаления блоков за запуск должен быть >= 0."
    except (ValueError, TypeError):
        return False, "Лимит удаления блоков должен быть целым числом."

    # Validate LOG_LEVEL
    log_level = str(data.get("LOG_LEVEL", "WARNING")).upper()
    if log_level not in ("DEBUG", "INFO", "WARNING"):
        return False, "Уровень логирования должен быть DEBUG, INFO или WARNING."

    # Validate timing / numeric thresholds
    numeric_checks = [
        ("SCROLL_STEP_PIXELS", 100, "Шаг прокрутки должен быть не менее 100 пикселей."),
        ("SCROLL_WAIT_MS", 500, "Пауза прокрутки должна быть не менее 500 мс."),
        ("AUTH_WAIT_TIMEOUT_MS", 30000, "Таймаут авторизации должен быть не менее 30 000 мс."),
        ("DOWNLOAD_TIMEOUT_MS", 10000, "Таймаут скачивания должен быть не менее 10 000 мс."),
        ("DOWNLOAD_MAX_RETRIES", 1, "Число повторов скачивания должно быть не менее 1."),
    ]
    for key, min_val, err_msg in numeric_checks:
        val = data.get(key)
        if val is not None:
            try:
                if int(val) < min_val:
                    return False, err_msg
            except (ValueError, TypeError):
                return False, f"Поле {key} должно быть целым числом."

    return True, None


def save_config(data: dict, path: str = None) -> bool:
    """Validates and saves configuration to JSON file."""
    is_valid, error = validate_config(data)
    if not is_valid:
        raise ValueError(error)

    target_path = path or CONFIG_PATH
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return True
