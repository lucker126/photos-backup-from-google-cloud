"""Live Log Terminal view for Google Photos Backup & Sync Bot.

Displays live colorized log messages with level filtering, auto-scroll,
search, copy-all, and quick access to app.log.
"""

import os
from tkinter import messagebox
import customtkinter as ctk

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_LOG_PATH = os.path.join(BASE_DIR, "app.log")


class LogsView(ctk.CTkFrame):
    """Terminal-like log journal with syntax highlighting and filtering."""

    def __init__(self, master, app_controller, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app_controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._all_records = []  # Stores list of dict: {level, message}

        self._build_header()
        self._build_controls_bar()
        self._build_log_area()

        # Load initial tail of app.log if exists
        self._load_app_log_tail()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 8))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Журнал событий и логи (Live)",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e")

        copy_btn = ctk.CTkButton(
            btn_box,
            text="📋 Копировать",
            font=ctk.CTkFont(size=12),
            height=32,
            width=90,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self._copy_all_logs,
        )
        copy_btn.pack(side="left", padx=4)

        open_file_btn = ctk.CTkButton(
            btn_box,
            text="📂 Открыть app.log",
            font=ctk.CTkFont(size=12),
            height=32,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self._open_log_file,
        )
        open_file_btn.pack(side="left", padx=4)

        clear_btn = ctk.CTkButton(
            btn_box,
            text="🗑️ Очистить",
            font=ctk.CTkFont(size=12),
            height=32,
            width=80,
            fg_color=("#fee2e2", "#7f1d1d"),
            text_color=("#b91c1c", "#fca5a5"),
            hover_color=("#fecaca", "#991b1b"),
            command=self.clear_logs,
        )
        clear_btn.pack(side="left", padx=4)

    def _build_controls_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        bar.grid_columnconfigure(2, weight=1)

        self.level_seg = ctk.CTkSegmentedButton(
            bar,
            values=["Все", "RUN / INFO", "WARNING", "ERROR"],
            command=lambda v: self._repopulate_textbox(),
        )
        self.level_seg.set("Все")
        self.level_seg.grid(row=0, column=0, padx=(0, 12))

        self.autoscroll_switch = ctk.CTkSwitch(
            bar,
            text="Автопрокрутка",
        )
        self.autoscroll_switch.select()
        self.autoscroll_switch.grid(row=0, column=1, padx=(0, 12))

        self.search_entry = ctk.CTkEntry(
            bar,
            placeholder_text="Поиск в журнале...",
            height=32,
        )
        self.search_entry.grid(row=0, column=2, sticky="ew")
        self.search_entry.bind("<KeyRelease>", lambda e: self._repopulate_textbox())

    def _build_log_area(self):
        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none",
            activate_scrollbars=True,
            corner_radius=12,
        )
        self.textbox.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))

        self.update_theme_colors()
        self.textbox.configure(state="disabled")

    def update_theme_colors(self, mode: str = None):
        """Sets tag foreground colors adapted to light or dark appearance mode."""
        current_mode = (mode or ctk.get_appearance_mode()).lower()
        tk_text = self.textbox._textbox
        if current_mode == "light":
            tk_text.tag_config("ERROR", foreground="#dc2626")
            tk_text.tag_config("WARNING", foreground="#d97706")
            tk_text.tag_config("INFO", foreground="#059669")
            tk_text.tag_config("RUN", foreground="#0284c7")
            tk_text.tag_config("DEBUG", foreground="#6b7280")
            tk_text.tag_config("DEFAULT", foreground="#1f2937")
        else:
            tk_text.tag_config("ERROR", foreground="#ef4444")
            tk_text.tag_config("WARNING", foreground="#f59e0b")
            tk_text.tag_config("INFO", foreground="#10b981")
            tk_text.tag_config("RUN", foreground="#06b6d4")
            tk_text.tag_config("DEBUG", foreground="#9ca3af")
            tk_text.tag_config("DEFAULT", foreground="#d1d5db")

    def append_record(self, level: str, message: str):
        """Appends a new live log record."""
        rec = {"level": level.upper(), "message": message}
        self._all_records.append(rec)
        if len(self._all_records) > 5000:
            self._all_records = self._all_records[-4000:]

        # Check if record matches active filter
        if self._matches_filter(rec):
            self._insert_record(rec)

    def _matches_filter(self, rec: dict) -> bool:
        lvl = rec["level"]
        selected_level = self.level_seg.get()

        if selected_level == "ERROR" and lvl not in ("ERROR", "CRITICAL"):
            return False
        elif selected_level == "WARNING" and lvl != "WARNING":
            return False
        elif selected_level == "RUN / INFO" and lvl not in ("RUN", "INFO"):
            return False

        query = self.search_entry.get().strip().lower()
        if query and query not in rec["message"].lower():
            return False

        return True

    def _insert_record(self, rec: dict):
        lvl = rec["level"]
        msg = rec["message"]

        self.textbox.configure(state="normal")
        tk_text = self.textbox._textbox

        tag = lvl if lvl in ("ERROR", "WARNING", "INFO", "RUN", "DEBUG") else "DEFAULT"
        tk_text.insert("end", msg + "\n", tag)

        if self.autoscroll_switch.get():
            self.textbox.see("end")

        self.textbox.configure(state="disabled")

    def _repopulate_textbox(self):
        """Re-filters all stored records and updates textbox."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")

        for rec in self._all_records:
            if self._matches_filter(rec):
                lvl = rec["level"]
                msg = rec["message"]
                tag = lvl if lvl in ("ERROR", "WARNING", "INFO", "RUN", "DEBUG") else "DEFAULT"
                self.textbox._textbox.insert("end", msg + "\n", tag)

        if self.autoscroll_switch.get():
            self.textbox.see("end")

        self.textbox.configure(state="disabled")

    def clear_logs(self):
        self._all_records.clear()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

    def _copy_all_logs(self):
        text = "\n".join(r["message"] for r in self._all_records)
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Скопировано", "Журнал логов скопирован в буфер обмена.")

    def _open_log_file(self):
        if os.path.exists(APP_LOG_PATH):
            os.startfile(APP_LOG_PATH)
        else:
            messagebox.showinfo("Файл не найден", f"{APP_LOG_PATH} еще не создан.")

    def _load_app_log_tail(self):
        """Loads last 80 lines from app.log if exists."""
        if not os.path.exists(APP_LOG_PATH):
            return

        try:
            with open(APP_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-80:]

            for line in lines:
                clean = line.rstrip()
                lvl = "INFO"
                if "[ERROR]" in clean:
                    lvl = "ERROR"
                elif "[WARNING]" in clean:
                    lvl = "WARNING"
                elif "[RUN]" in clean:
                    lvl = "RUN"
                elif "[DEBUG]" in clean:
                    lvl = "DEBUG"

                self.append_record(lvl, clean)
        except Exception:
            pass
