import os
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import shutil

import google_photos_bot as bot


class MockDownloadContext:
    def __init__(self, download=None, error=None):
        self.download = download
        self.error = error

    def __enter__(self):
        info = MagicMock()
        if self.error:
            type(info).value = property(lambda s: (_ for _ in ()).throw(self.error))
        else:
            info.value = self.download
        return info

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.error:
            raise self.error
        return False


class TestDownloadRetryAndConfig(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_get_int_config_defaults_and_aliases(self):
        with patch.dict(bot.config, {"DOWNLOAD_TIMEOUT_MS": 180000}, clear=True):
            self.assertEqual(bot.get_int_config("DOWNLOAD_TIMEOUT_MS", 120000, 10000), 180000)

        # Lowercase alias fallback
        with patch.dict(bot.config, {"download_timeout_ms": "240000"}, clear=True):
            self.assertEqual(bot.get_int_config("DOWNLOAD_TIMEOUT_MS", 120000, 10000), 240000)

        # Minimum enforcement
        with patch.dict(bot.config, {"DOWNLOAD_MAX_RETRIES": 0}, clear=True):
            self.assertEqual(bot.get_int_config("DOWNLOAD_MAX_RETRIES", 3, 1), 1)

        # Default fallback on invalid or missing value
        with patch.dict(bot.config, {"DOWNLOAD_MAX_RETRIES": "invalid"}, clear=True):
            self.assertEqual(bot.get_int_config("DOWNLOAD_MAX_RETRIES", 3, 1), 3)

    def test_select_block_checkbox_already_checked(self):
        page = MagicMock()
        static_cb = MagicMock()
        static_cb.get_attribute.return_value = "true"

        result = bot.select_block_checkbox(page, static_cb, "2026-05-10", force_reselect=False)
        self.assertTrue(result)
        static_cb.click.assert_not_called()

    def test_select_block_checkbox_force_reselect(self):
        page = MagicMock()
        static_cb = MagicMock()
        static_cb.get_attribute.return_value = "true"

        result = bot.select_block_checkbox(page, static_cb, "2026-05-10", force_reselect=True)
        self.assertTrue(result)
        # Should click to uncheck, then click to check
        self.assertEqual(static_cb.click.call_count, 2)
        page.wait_for_selector.assert_called_once()

    def test_select_block_checkbox_js_fallback_success(self):
        page = MagicMock()
        static_cb = MagicMock()
        # Not checked initially, checked after JS click
        static_cb.get_attribute.side_effect = ["false", "true"]
        # Playwright click fails
        static_cb.click.side_effect = Exception("Element obscured")

        result = bot.select_block_checkbox(page, static_cb, "2026-05-10", max_attempts=1)
        self.assertTrue(result)
        static_cb.evaluate.assert_called_with("el => el.click()")

    def test_select_block_checkbox_all_fail(self):
        page = MagicMock()
        static_cb = MagicMock()
        static_cb.get_attribute.return_value = "false"
        static_cb.click.side_effect = Exception("Click error")
        static_cb.evaluate.side_effect = Exception("JS click error")

        result = bot.select_block_checkbox(page, static_cb, "2026-05-10", max_attempts=2)
        self.assertFalse(result)

    def test_download_block_with_retry_success_first_attempt(self):
        page = MagicMock()
        page.is_closed.return_value = False
        static_cb = MagicMock()
        static_cb.get_attribute.return_value = "true"

        mock_download = MagicMock()
        mock_download.suggested_filename = "photos_batch.zip"

        def fake_save_as(dest):
            with open(dest, "wb") as f:
                f.write(b"PK\x03\x04valid_zip_content")

        mock_download.save_as.side_effect = fake_save_as
        page.expect_download.return_value = MockDownloadContext(download=mock_download)

        with patch("google_photos_bot.is_login_page", return_value=False):
            download_path = bot.download_block_with_retry(
                page=page,
                static_cb=static_cb,
                safe_label="2026-05-10",
                temp_dir=self.test_dir,
                timeout_ms=1000,
                max_retries=3
            )

        self.assertTrue(os.path.exists(download_path))
        self.assertEqual(os.path.basename(download_path), "photos_batch.zip")
        self.assertEqual(page.keyboard.press.call_count, 1)
        page.keyboard.press.assert_called_with("Shift+D")

    def test_download_block_with_retry_recovers_after_timeout(self):
        page = MagicMock()
        page.is_closed.return_value = False
        static_cb = MagicMock()
        static_cb.get_attribute.return_value = "true"

        mock_download = MagicMock()
        mock_download.suggested_filename = "recovered.zip"

        def fake_save_as(dest):
            with open(dest, "wb") as f:
                f.write(b"PK\x03\x04valid_recovered_zip")

        mock_download.save_as.side_effect = fake_save_as

        # Attempt 1: Timeout; Attempt 2: Success
        ctx_fail = MockDownloadContext(error=TimeoutError("Timeout 120000ms exceeded"))
        ctx_success = MockDownloadContext(download=mock_download)
        page.expect_download.side_effect = [ctx_fail, ctx_success]

        with patch("google_photos_bot.is_login_page", return_value=False):
            download_path = bot.download_block_with_retry(
                page=page,
                static_cb=static_cb,
                safe_label="2026-05-10",
                temp_dir=self.test_dir,
                timeout_ms=1000,
                max_retries=3
            )

        self.assertTrue(os.path.exists(download_path))
        self.assertEqual(os.path.basename(download_path), "recovered.zip")
        self.assertEqual(page.keyboard.press.call_count, 2)

    def test_download_block_with_retry_handles_zero_byte_download(self):
        page = MagicMock()
        page.is_closed.return_value = False
        static_cb = MagicMock()
        static_cb.get_attribute.return_value = "true"

        mock_download_empty = MagicMock()
        mock_download_empty.suggested_filename = "empty.zip"
        def fake_save_empty(dest):
            with open(dest, "wb") as f:
                pass  # 0 bytes
        mock_download_empty.save_as.side_effect = fake_save_empty

        mock_download_valid = MagicMock()
        mock_download_valid.suggested_filename = "valid.zip"
        def fake_save_valid(dest):
            with open(dest, "wb") as f:
                f.write(b"data")
        mock_download_valid.save_as.side_effect = fake_save_valid

        ctx1 = MockDownloadContext(download=mock_download_empty)
        ctx2 = MockDownloadContext(download=mock_download_valid)
        page.expect_download.side_effect = [ctx1, ctx2]

        with patch("google_photos_bot.is_login_page", return_value=False):
            download_path = bot.download_block_with_retry(
                page=page,
                static_cb=static_cb,
                safe_label="2026-05-10",
                temp_dir=self.test_dir,
                timeout_ms=1000,
                max_retries=3
            )

        self.assertTrue(os.path.exists(download_path))
        self.assertEqual(os.path.basename(download_path), "valid.zip")
        self.assertEqual(page.keyboard.press.call_count, 2)

    def test_download_block_with_retry_max_retries_exceeded(self):
        page = MagicMock()
        page.is_closed.return_value = False
        static_cb = MagicMock()
        static_cb.get_attribute.return_value = "true"

        ctx_fail = MockDownloadContext(error=TimeoutError("Timeout 120000ms exceeded"))
        page.expect_download.side_effect = [ctx_fail, ctx_fail, ctx_fail]

        with patch("google_photos_bot.is_login_page", return_value=False):
            with self.assertRaises(TimeoutError):
                bot.download_block_with_retry(
                    page=page,
                    static_cb=static_cb,
                    safe_label="2026-05-10",
                    temp_dir=self.test_dir,
                    timeout_ms=1000,
                    max_retries=3
                )

        self.assertEqual(page.keyboard.press.call_count, 3)

    def test_download_block_with_retry_browser_closed(self):
        page = MagicMock()
        page.is_closed.return_value = True
        static_cb = MagicMock()

        with self.assertRaisesRegex(RuntimeError, "закрыто"):
            bot.download_block_with_retry(
                page=page,
                static_cb=static_cb,
                safe_label="2026-05-10",
                temp_dir=self.test_dir,
                timeout_ms=1000,
                max_retries=3
            )

    def test_wait_for_delete_completion_detached_immediately(self):
        page = MagicMock()
        # count() is 0 (already detached)
        page.locator.return_value.count.return_value = 0
        result = bot.wait_for_delete_completion(page, "2026-05-10", timeout_ms=500)
        self.assertTrue(result)

    def test_wait_for_delete_completion_confirms_delayed_dialog(self):
        page = MagicMock()
        state = {"dialog_visible": True, "block_count": 1}

        def fake_locator(selector):
            loc = MagicMock()
            if "dialog" in selector:
                loc.count.side_effect = lambda: 1 if state["dialog_visible"] else 0
            else:
                loc.count.side_effect = lambda: state["block_count"]
            return loc

        page.locator.side_effect = fake_locator

        def fake_confirm(p, timeout_ms=2000):
            state["dialog_visible"] = False
            state["block_count"] = 0
            return True

        with patch("google_photos_bot.confirm_delete_if_required", side_effect=fake_confirm) as mock_confirm:
            result = bot.wait_for_delete_completion(page, "2026-05-10", timeout_ms=2000)
            self.assertTrue(result)
            mock_confirm.assert_called_once()

    def test_wait_for_delete_completion_timeout_raises(self):
        page = MagicMock()
        # Always visible (count = 1)
        page.locator.return_value.count.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "Google Photos did not remove"):
            bot.wait_for_delete_completion(page, "2026-05-10", timeout_ms=100)


if __name__ == "__main__":
    unittest.main()
