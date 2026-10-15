"""Thread-safe Bot Runner and Queue Logging Handler for GUI.

Executes google_photos_bot in a background thread and transmits logs and
lifecycle events to the CustomTkinter UI via queue.Queue.
"""

import logging
import queue
import threading
from typing import Any, Optional


class QueueLogHandler(logging.Handler):
    """Logging handler that transmits log records into a thread-safe Queue."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        # Default format if not set
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.log_queue.put(
                {
                    "type": "log",
                    "level": record.levelname,
                    "message": msg,
                    "created": record.created,
                    "name": record.name,
                }
            )
        except Exception:
            self.handleError(record)


class BotRunner(threading.Thread):
    """Orchestrator thread for running the bot without freezing the UI."""

    def __init__(self, event_queue: queue.Queue):
        super().__init__(name="BotRunnerThread", daemon=True)
        self.event_queue = event_queue
        self.stop_event = threading.Event()
        self._is_running = False
        self._handler: Optional[QueueLogHandler] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def request_stop(self):
        """Signals the bot to stop gracefully between blocks."""
        if self._is_running:
            self.stop_event.set()
            self.event_queue.put({"type": "status", "status": "stopping"})

    def run(self):
        self._is_running = True
        self.stop_event.clear()

        try:
            import google_photos_bot as bot
            bot.ensure_file_logging()
        except Exception:
            pass

        # Attach QueueLogHandler to root logger
        root_logger = logging.getLogger()
        self._handler = QueueLogHandler(self.event_queue)
        root_logger.addHandler(self._handler)

        self.event_queue.put({"type": "status", "status": "running"})

        stats = None
        try:
            import google_photos_bot as bot

            stats = bot.run(stop_event=self.stop_event)

            if stats is None and not self.stop_event.is_set():
                raise RuntimeError("Синхронизация прервана: статистика сессии не получена.")

            if self.stop_event.is_set():
                self.event_queue.put({"type": "status", "status": "stopped", "stats": stats})
            else:
                self.event_queue.put({"type": "status", "status": "finished", "stats": stats})
        except Exception as e:
            logging.exception(f"Ошибка выполнения бота: {e}")
            self.event_queue.put(
                {
                    "type": "status",
                    "status": "error",
                    "error": str(e),
                    "stats": stats,
                }
            )
        finally:
            self._is_running = False
            if self._handler:
                root_logger.removeHandler(self._handler)
                self._handler = None
