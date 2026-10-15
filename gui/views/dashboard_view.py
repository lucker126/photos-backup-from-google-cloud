"""Dashboard view for Google Photos Backup & Sync Bot.

Displays live status, KPI metric cards, progress indicators, action buttons,
and a mini live session log feed.
"""

import customtkinter as ctk
from datetime import datetime
import manifest_report as mr
from gui.config_manager import load_config


class MetricCard(ctk.CTkFrame):
    """Modern rounded KPI metric tile with title, value and subtitle."""

    def __init__(self, master, title: str, initial_value: str = "—", icon: str = "", **kwargs):
        super().__init__(master, corner_radius=12, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        header_text = f"{icon} {title}".strip()
        self.title_label = ctk.CTkLabel(
            self,
            text=header_text,
            font=ctk.CTkFont(size=12, weight="normal"),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        self.value_label = ctk.CTkLabel(
            self,
            text=initial_value,
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        )
        self.value_label.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

    def set_value(self, value: str):
        self.value_label.configure(text=value)


class DashboardView(ctk.CTkFrame):
    """Main dashboard screen."""

    def __init__(self, master, app_controller, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app_controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._session_new_files = 0
        self._session_deleted_files = 0

        self._build_header()
        self._build_metric_cards()
        self._build_progress_section()
        self._build_controls()
        self._build_mini_log()

        # Initial metrics load
        self.refresh_metrics()

    def _build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        self.title_lbl = ctk.CTkLabel(
            title_box,
            text="Дашборд синхронизации",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.title_lbl.pack(side="left")

        # Badges frame on right
        badges_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        badges_frame.grid(row=0, column=1, sticky="e")

        self.status_pill = ctk.CTkLabel(
            badges_frame,
            text="● Готов к работе",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("gray85", "gray25"),
            corner_radius=8,
            padx=12,
            pady=6,
        )
        self.status_pill.pack(side="left", padx=6)

        self.safety_pill = ctk.CTkLabel(
            badges_frame,
            text="🛡️ DRY RUN",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#dcfce7", "#14532d"),
            text_color=("#166534", "#86efac"),
            corner_radius=8,
            padx=12,
            pady=6,
        )
        self.safety_pill.pack(side="left", padx=6)

    def _build_metric_cards(self):
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        for i in range(4):
            cards_frame.grid_columnconfigure(i, weight=1, uniform="kpi")

        self.card_files = MetricCard(cards_frame, "Файлов в архиве", icon="📁")
        self.card_files.grid(row=0, column=0, padx=6, pady=6, sticky="ew")

        self.card_size = MetricCard(cards_frame, "Общий объем", icon="💾")
        self.card_size.grid(row=0, column=1, padx=6, pady=6, sticky="ew")

        self.card_downloaded = MetricCard(cards_frame, "Скачано за сеанс", initial_value="0", icon="📥")
        self.card_downloaded.grid(row=0, column=2, padx=6, pady=6, sticky="ew")

        self.card_deleted = MetricCard(cards_frame, "Удалено из облака", initial_value="0", icon="🗑️")
        self.card_deleted.grid(row=0, column=3, padx=6, pady=6, sticky="ew")

    def _build_progress_section(self):
        progress_card = ctk.CTkFrame(self, corner_radius=12)
        progress_card.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        progress_card.grid_columnconfigure(0, weight=1)

        self.progress_title = ctk.CTkLabel(
            progress_card,
            text="Текущее состояние: Ожидание запуска",
            font=ctk.CTkFont(size=14, weight="normal"),
            anchor="w",
        )
        self.progress_title.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(progress_card, height=10, corner_radius=5)
        self.progress_bar.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")
        self.progress_bar.set(0)

    def _build_controls(self):
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=10)

        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="▶ Запустить синхронизацию",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=42,
            fg_color=("#16a34a", "#22c55e"),
            hover_color=("#15803d", "#16a34a"),
            command=self.app.start_bot,
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="🛑 Остановить",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            fg_color=("#dc2626", "#ef4444"),
            hover_color=("#b91c1c", "#dc2626"),
            state="disabled",
            command=self.app.stop_bot,
        )
        self.stop_btn.pack(side="left", padx=10)

        self.refresh_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Обновить метрики",
            font=ctk.CTkFont(size=13),
            height=42,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self.refresh_metrics,
        )
        self.refresh_btn.pack(side="left", padx=10)

    def _build_mini_log(self):
        log_frame = ctk.CTkFrame(self, corner_radius=12)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=(10, 20))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(log_frame, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        top_bar.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            top_bar,
            text="Быстрый лог сессии",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        view_all_btn = ctk.CTkButton(
            top_bar,
            text="Открыть полный журнал ➜",
            font=ctk.CTkFont(size=12),
            height=28,
            fg_color="transparent",
            text_color=("#2563eb", "#60a5fa"),
            hover=False,
            command=lambda: self.app.show_view("logs"),
        )
        view_all_btn.grid(row=0, column=1, sticky="e")

        self.mini_log_text = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none",
            activate_scrollbars=True,
        )
        self.mini_log_text.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 14))
        self.mini_log_text.configure(state="disabled")

    def append_log_line(self, line: str):
        """Appends a line to the mini log window."""
        self.mini_log_text.configure(state="normal")
        self.mini_log_text.insert("end", line + "\n")
        try:
            line_count = int(float(self.mini_log_text.index("end-1c").split(".")[0]))
            if line_count > 250:
                self.mini_log_text.delete("1.0", "50.0")
        except Exception:
            pass
        self.mini_log_text.see("end")
        self.mini_log_text.configure(state="disabled")

        # Parse real-time progress cues from log line
        if "Скачан архив" in line or "Порция:" in line:
            self.progress_title.configure(text=f"Текущее действие: {line.strip()}")
        elif "Удаляем фото из облака" in line:
            self.progress_title.configure(text="Текущее действие: Удаление фото из облака...")
        elif "Найдена группа:" in line:
            self.progress_title.configure(text=f"Текущее действие: {line.strip()}")

    def set_bot_status(self, status: str, error_msg: str = None):
        """Updates dashboard elements when bot status changes."""
        if status == "running":
            self.status_pill.configure(
                text="● Синхронизация выполняется...",
                fg_color=("#dbeafe", "#1e3a8a"),
                text_color=("#1d4ed8", "#93c5fd"),
            )
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.progress_title.configure(text="Текущее действие: Инициализация Chromium...")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
        elif status == "stopping":
            self.status_pill.configure(
                text="● Остановка...",
                fg_color=("#fef3c7", "#78350f"),
                text_color=("#b45309", "#fcd34d"),
            )
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self.progress_title.configure(text="Текущее действие: Завершение текущего блока и выход...")
        elif status in ("stopped", "finished"):
            self.status_pill.configure(
                text="● Завершено",
                fg_color=("gray85", "gray25"),
                text_color=("black", "white"),
            )
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(1.0)
            self.progress_title.configure(text="Текущее состояние: Завершено успешно.")
            self.refresh_metrics()
        elif status == "error":
            self.status_pill.configure(
                text="● Ошибка",
                fg_color=("#fee2e2", "#7f1d1d"),
                text_color=("#b91c1c", "#fca5a5"),
            )
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)
            err_text = f"Ошибка: {error_msg}" if error_msg else "Произошла ошибка при выполнении"
            self.progress_title.configure(text=f"Текущее состояние: {err_text}")
            self.refresh_metrics()

    def update_session_stats(self, stats: dict):
        """Updates stats reported directly from bot."""
        if not stats or not isinstance(stats, dict):
            return
        downloaded = stats.get("new_downloaded", 0)
        deleted = stats.get("total_deleted", 0)
        self.card_downloaded.set_value(f"+{downloaded:,}".replace(",", " "))
        self.card_deleted.set_value(f"{deleted:,}".replace(",", " "))

    def refresh_metrics(self):
        """Reloads config and manifest to update cards and badges."""
        cfg = load_config()

        # Update Safety Badge
        dry_run = cfg.get("DRY_RUN_DELETE", True)
        allow_delete = cfg.get("ALLOW_CLOUD_DELETE", True)
        if dry_run or not allow_delete:
            self.safety_pill.configure(
                text="🛡️ DRY RUN (Безопасно)",
                fg_color=("#dcfce7", "#14532d"),
                text_color=("#166534", "#86efac"),
            )
        else:
            self.safety_pill.configure(
                text="⚠️ РЕАЛЬНОЕ УДАЛЕНИЕ",
                fg_color=("#fee2e2", "#7f1d1d"),
                text_color=("#b91c1c", "#fca5a5"),
            )

        # Load Manifest Summary
        state_file = cfg.get("STATE_FILE", "backup_manifest.json")
        resolved_manifest = mr.resolve_path(state_file)
        if mr.os.path.exists(resolved_manifest):
            try:
                manifest_data = mr.load_json(resolved_manifest)
                summary = mr.collect_summary(
                    manifest_data,
                    resolved_manifest,
                    mr.date.today(),
                    cfg.get("DAYS_TO_KEEP_IN_CLOUD", 180),
                )
                self.card_files.set_value(f"{summary['files_count']:,}".replace(",", " "))
                self.card_size.set_value(mr.format_size(summary["stats_size"]))
            except Exception:
                pass
