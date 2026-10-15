"""Main application window for Google Photos Backup & Sync Bot.

Integrates CustomTkinter Fluent UI, sidebar navigation, view switching,
thread-safe background BotRunner execution, and real-time event queue polling.
"""

import queue
import time
from tkinter import messagebox
import customtkinter as ctk

from gui.runner import BotRunner
from gui.views.dashboard_view import DashboardView
from gui.views.settings_view import SettingsView
from gui.views.manifest_view import ManifestView
from gui.views.logs_view import LogsView


class App(ctk.CTk):
    """Main desktop application window."""

    def __init__(self):
        super().__init__()

        # Window Configuration
        self.title("Google Photos Backup & Sync")
        self.geometry("1120x740")
        self.minsize(960, 640)

        # Appearance
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Communication Queue & Background Runner
        self.event_queue = queue.Queue()
        self.bot_runner = None

        # Main Layout (Sidebar + Content)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_views()

        # Handle close event
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Start Queue Polling loop
        self.after(50, self._process_queue)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)

        # App Brand / Title
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=20, pady=(24, 20), sticky="ew")

        brand_title = ctk.CTkLabel(
            brand_frame,
            text="📷 Photos Backup",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        )
        brand_title.pack(fill="x")

        brand_sub = ctk.CTkLabel(
            brand_frame,
            text="Google Photos Sync Hub",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray65"),
            anchor="w",
        )
        brand_sub.pack(fill="x")

        # Navigation Buttons
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "🚀  Дашборд"),
            ("settings", "⚙️  Настройки"),
            ("manifest", "📊  Манифест"),
            ("logs", "📜  Журнал логов"),
        ]

        for idx, (view_id, label) in enumerate(nav_items, start=1):
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                font=ctk.CTkFont(size=14, weight="normal"),
                height=40,
                corner_radius=8,
                anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray25"),
                command=lambda v=view_id: self.show_view(v),
            )
            btn.grid(row=idx, column=0, padx=14, pady=4, sticky="ew")
            self.nav_buttons[view_id] = btn

        # Bottom Sidebar Widget: Appearance & Status
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.grid(row=6, column=0, padx=14, pady=20, sticky="ew")

        theme_lbl = ctk.CTkLabel(
            bottom_frame,
            text="Тема интерфейса:",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        theme_lbl.pack(fill="x", pady=(0, 4))

        self.theme_opt = ctk.CTkOptionMenu(
            bottom_frame,
            values=["Dark", "Light", "System"],
            command=self._change_theme,
            height=30,
        )
        self.theme_opt.set("Dark")
        self.theme_opt.pack(fill="x", pady=(0, 10))

        self.sidebar_status = ctk.CTkLabel(
            bottom_frame,
            text="● Готов к работе",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        self.sidebar_status.pack(fill="x")

    def _build_content_views(self):
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        self.views = {
            "dashboard": DashboardView(self.content_container, app_controller=self),
            "settings": SettingsView(self.content_container, app_controller=self),
            "manifest": ManifestView(self.content_container, app_controller=self),
            "logs": LogsView(self.content_container, app_controller=self),
        }

        # Expose references for cross-view updates
        self.dashboard_view = self.views["dashboard"]
        self.settings_view = self.views["settings"]
        self.manifest_view = self.views["manifest"]
        self.logs_view = self.views["logs"]

        # Show Dashboard initially
        self.show_view("dashboard")

    def show_view(self, view_name: str):
        """Switches the active content view and highlights active nav button."""
        for name, view in self.views.items():
            if name == view_name:
                view.grid(row=0, column=0, sticky="nsew")
                self.nav_buttons[name].configure(
                    fg_color=("gray75", "gray30"),
                    font=ctk.CTkFont(size=14, weight="bold"),
                )
            else:
                view.grid_forget()
                self.nav_buttons[name].configure(
                    fg_color="transparent",
                    font=ctk.CTkFont(size=14, weight="normal"),
                )

    def _change_theme(self, new_mode: str):
        ctk.set_appearance_mode(new_mode)
        if hasattr(self, "logs_view") and hasattr(self.logs_view, "update_theme_colors"):
            self.logs_view.update_theme_colors(new_mode)

    def start_bot(self):
        """Starts the bot in the background worker thread."""
        if self.bot_runner and self.bot_runner.is_running:
            return

        self.bot_runner = BotRunner(self.event_queue)
        self.bot_runner.start()

    def stop_bot(self):
        """Signals the bot to stop."""
        if self.bot_runner and self.bot_runner.is_running:
            self.bot_runner.request_stop()

    def _process_queue(self):
        """Processes logs and lifecycle events from the background thread."""
        try:
            while True:
                try:
                    item = self.event_queue.get_nowait()
                except queue.Empty:
                    break

                msg_type = item.get("type")
                if msg_type == "log":
                    lvl = item.get("level", "INFO")
                    msg = item.get("message", "")
                    self.logs_view.append_record(lvl, msg)
                    self.dashboard_view.append_log_line(msg)

                elif msg_type == "status":
                    status = item.get("status")
                    err = item.get("error")
                    stats = item.get("stats")

                    self.dashboard_view.set_bot_status(status, err)

                    if status == "running":
                        self.sidebar_status.configure(
                            text="● Выполняется...",
                            text_color=("#2563eb", "#60a5fa"),
                        )
                    elif status == "stopping":
                        self.sidebar_status.configure(
                            text="● Остановка...",
                            text_color=("#d97706", "#fbbf24"),
                        )
                    elif status in ("stopped", "finished"):
                        self.sidebar_status.configure(
                            text="● Готов к работе",
                            text_color=("gray40", "gray70"),
                        )
                        if stats:
                            self.dashboard_view.update_session_stats(stats)
                        self.manifest_view.reload_manifest()
                    elif status == "error":
                        self.sidebar_status.configure(
                            text="● Ошибка",
                            text_color=("#dc2626", "#f87171"),
                        )
                        if stats:
                            self.dashboard_view.update_session_stats(stats)
                        self.manifest_view.reload_manifest()
        except Exception:
            pass
        finally:
            # Always schedule next poll even if an exception occurred
            self.after(50, self._process_queue)

    def on_closing(self):
        """Handles application window closure."""
        if self.bot_runner and self.bot_runner.is_running:
            confirm = messagebox.askyesno(
                "Синхронизация активна",
                "Бот сейчас выполняет резервное копирование!\n\n"
                "Остановить бота и безопасно закрыть приложение?",
                icon="warning",
            )
            if confirm:
                self.title("Google Photos Backup & Sync — Остановка Chromium...")
                self.sidebar_status.configure(
                    text="● Завершение работы...",
                    text_color=("#dc2626", "#f87171"),
                )
                self.bot_runner.request_stop()
                self._wait_and_destroy(start_time=time.time())
        else:
            self.destroy()

    def _wait_and_destroy(self, start_time: float):
        if self.bot_runner and self.bot_runner.is_alive() and (time.time() - start_time < 5.0):
            self.after(150, lambda: self._wait_and_destroy(start_time))
        else:
            self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
