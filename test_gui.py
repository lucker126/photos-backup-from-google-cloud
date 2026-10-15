"""Unit tests for CustomTkinter GUI components and background worker."""

import json
import logging
import os
import queue
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from gui.config_manager import (
    DEFAULT_CONFIG,
    load_config,
    save_config,
    validate_config,
)
from gui.runner import BotRunner, QueueLogHandler


class TestQueueLogHandler(unittest.TestCase):
    def setUp(self):
        self.q = queue.Queue()
        self.handler = QueueLogHandler(self.q)
        self.logger = logging.getLogger("test_logger")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

    def tearDown(self):
        self.logger.removeHandler(self.handler)

    def test_emit_puts_record_in_queue(self):
        self.logger.info("Тестовое информационное сообщение")
        self.assertFalse(self.q.empty())
        item = self.q.get_nowait()
        self.assertEqual(item["type"], "log")
        self.assertEqual(item["level"], "INFO")
        self.assertIn("Тестовое информационное сообщение", item["message"])

    def test_emit_multiple_levels(self):
        self.logger.warning("Предупреждение!")
        self.logger.error("Ошибка!")
        items = []
        while not self.q.empty():
            items.append(self.q.get_nowait())
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["level"], "WARNING")
        self.assertEqual(items[1]["level"], "ERROR")


class TestBotRunner(unittest.TestCase):
    def setUp(self):
        self.q = queue.Queue()
        self.runner = BotRunner(self.q)

    def test_runner_initial_state(self):
        self.assertFalse(self.runner.is_running)
        self.assertFalse(self.runner.stop_event.is_set())

    @patch("google_photos_bot.run")
    def test_runner_successful_run(self, mock_run):
        mock_run.return_value = {"new_downloaded": 5, "total_deleted": 2}
        self.runner.start()
        self.runner.join(timeout=3.0)

        self.assertFalse(self.runner.is_running)

        events = []
        while not self.q.empty():
            events.append(self.q.get_nowait())

        status_events = [e for e in events if e.get("type") == "status"]
        self.assertTrue(len(status_events) >= 2)
        self.assertEqual(status_events[0]["status"], "running")
        self.assertEqual(status_events[-1]["status"], "finished")
        self.assertEqual(status_events[-1]["stats"]["new_downloaded"], 5)

    @patch("google_photos_bot.run")
    def test_runner_stop_request(self, mock_run):
        def fake_run(stop_event=None):
            # Simulate waiting for stop
            while not stop_event.is_set():
                time.sleep(0.01)
            return {"new_downloaded": 0, "total_deleted": 0}

        mock_run.side_effect = fake_run

        self.runner.start()
        time.sleep(0.05)
        self.assertTrue(self.runner.is_running)

        self.runner.request_stop()
        self.runner.join(timeout=3.0)
        self.assertFalse(self.runner.is_running)

        events = []
        while not self.q.empty():
            events.append(self.q.get_nowait())

        statuses = [e.get("status") for e in events if e.get("type") == "status"]
        self.assertIn("running", statuses)
        self.assertIn("stopping", statuses)
        self.assertIn("stopped", statuses)

    @patch("google_photos_bot.run")
    def test_runner_exception_handling(self, mock_run):
        mock_run.side_effect = RuntimeError("Playwright connection failed")

        self.runner.start()
        self.runner.join(timeout=3.0)
        self.assertFalse(self.runner.is_running)

        events = []
        while not self.q.empty():
            events.append(self.q.get_nowait())

        error_events = [e for e in events if e.get("type") == "status" and e.get("status") == "error"]
        self.assertEqual(len(error_events), 1)
        self.assertIn("Playwright connection failed", error_events[0]["error"])

    @patch("google_photos_bot.run")
    def test_runner_none_stats_raises_error(self, mock_run):
        mock_run.return_value = None

        self.runner.start()
        self.runner.join(timeout=3.0)
        self.assertFalse(self.runner.is_running)

        events = []
        while not self.q.empty():
            events.append(self.q.get_nowait())

        error_events = [e for e in events if e.get("type") == "status" and e.get("status") == "error"]
        self.assertEqual(len(error_events), 1)
        self.assertIn("статистика сессии не получена", error_events[0]["error"])



class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_config_defaults(self):
        cfg = load_config(self.config_file)
        self.assertEqual(cfg["DEST_DIR"], DEFAULT_CONFIG["DEST_DIR"])
        self.assertEqual(cfg["DAYS_TO_KEEP_IN_CLOUD"], 180)

    def test_load_config_with_file_merge(self):
        data = {"DEST_DIR": "E:\\Backups", "DAYS_TO_KEEP_IN_CLOUD": 90}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        cfg = load_config(self.config_file)
        self.assertEqual(cfg["DEST_DIR"], "E:\\Backups")
        self.assertEqual(cfg["DAYS_TO_KEEP_IN_CLOUD"], 90)
        self.assertEqual(cfg["HEADLESS_MODE"], False)  # from default

    def test_validate_config_success(self):
        valid_cfg = {
            "DEST_DIR": "C:\\Archive",
            "DAYS_TO_KEEP_IN_CLOUD": 60,
            "STOP_AT_DATE": "2024-05-01",
            "MAX_DELETE_BLOCKS_PER_RUN": 5,
            "LOG_LEVEL": "INFO",
            "SCROLL_STEP_PIXELS": 500,
            "SCROLL_WAIT_MS": 1500,
            "AUTH_WAIT_TIMEOUT_MS": 300000,
            "DOWNLOAD_TIMEOUT_MS": 120000,
            "DOWNLOAD_MAX_RETRIES": 3,
        }
        ok, err = validate_config(valid_cfg)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_validate_config_empty_dest(self):
        cfg = {"DEST_DIR": "   "}
        ok, err = validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("DEST_DIR", err)

    def test_validate_config_negative_days(self):
        cfg = {"DEST_DIR": "D:\\", "DAYS_TO_KEEP_IN_CLOUD": -1}
        ok, err = validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn(">= 0", err)

    def test_validate_config_invalid_date_format(self):
        cfg = {"DEST_DIR": "D:\\", "STOP_AT_DATE": "01-05-2024"}
        ok, err = validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("ГГГГ-ММ-ДД", err)

    def test_validate_config_invalid_log_level(self):
        cfg = {"DEST_DIR": "D:\\", "LOG_LEVEL": "TRACE"}
        ok, err = validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("DEBUG, INFO или WARNING", err)

    def test_validate_config_timing_thresholds(self):
        cfg = {"DEST_DIR": "D:\\", "SCROLL_STEP_PIXELS": 50}
        ok, err = validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("Шаг прокрутки", err)

    def test_validate_config_non_numeric_timing(self):
        cfg = {"DEST_DIR": "D:\\", "SCROLL_STEP_PIXELS": "fast"}
        ok, err = validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("целым числом", err)

    def test_reload_config_updates_logger_level(self):
        import google_photos_bot as bot
        with patch("json.load", return_value={"LOG_LEVEL": "DEBUG"}):
            bot.reload_config()
            self.assertEqual(logging.getLogger().level, logging.DEBUG)
        # Restore to default
        with patch("json.load", return_value={"LOG_LEVEL": "WARNING"}):
            bot.reload_config()
            self.assertEqual(logging.getLogger().level, bot.RUN_LEVEL)


    def test_save_config_writes_valid_json(self):
        data = {
            "DEST_DIR": "D:\\Photos",
            "DAYS_TO_KEEP_IN_CLOUD": 120,
            "ALLOW_CLOUD_DELETE": True,
            "DRY_RUN_DELETE": True,
        }
        save_config(data, self.config_file)
        self.assertTrue(os.path.exists(self.config_file))

        with open(self.config_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["DEST_DIR"], "D:\\Photos")
        self.assertEqual(loaded["DAYS_TO_KEEP_IN_CLOUD"], 120)


class TestLogsFiltering(unittest.TestCase):
    def test_log_matching_logic(self):
        from gui.views.logs_view import LogsView

        # Test filter matching logic without creating graphical window
        rec_info = {"level": "INFO", "message": "22:15:00 [INFO] Скачан архив photos.zip"}
        rec_err = {"level": "ERROR", "message": "22:15:10 [ERROR] Connection lost"}
        rec_warn = {"level": "WARNING", "message": "22:15:05 [WARNING] Retry needed"}

        # Custom mock for LogsView filter testing
        mock_view = MagicMock()
        mock_view.level_seg.get.return_value = "Все"
        mock_view.search_entry.get.return_value = ""
        self.assertTrue(LogsView._matches_filter(mock_view, rec_info))
        self.assertTrue(LogsView._matches_filter(mock_view, rec_err))

        mock_view.level_seg.get.return_value = "ERROR"
        self.assertFalse(LogsView._matches_filter(mock_view, rec_info))
        self.assertTrue(LogsView._matches_filter(mock_view, rec_err))

        mock_view.level_seg.get.return_value = "Все"
        mock_view.search_entry.get.return_value = "archive"
        self.assertFalse(LogsView._matches_filter(mock_view, rec_info))  # "архив" vs "archive"
        mock_view.search_entry.get.return_value = "архив"
        self.assertTrue(LogsView._matches_filter(mock_view, rec_info))


if __name__ == "__main__":
    unittest.main()
