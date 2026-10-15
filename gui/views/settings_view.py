"""Settings view for Google Photos Backup & Sync Bot.

Visual configuration editor for config.json with native folder picker,
safety status badges, sliders, validation, and advanced timings.
"""

import os
from datetime import date, timedelta
from tkinter import filedialog, messagebox
import customtkinter as ctk

from gui.config_manager import DEFAULT_CONFIG, CONFIG_PATH, load_config, save_config, validate_config


class SettingsView(ctk.CTkScrollableFrame):
    """Configuration screen."""

    def __init__(self, master, app_controller, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app_controller

        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_storage_section()
        self._build_cloud_safety_section()
        self._build_run_params_section()
        self._build_advanced_section()
        self._build_action_buttons()

        self.load_settings()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 15))

        title = ctk.CTkLabel(
            header,
            text="Настройки синхронизации",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        )
        title.pack(side="left")

        self.notify_lbl = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#16a34a",
        )
        self.notify_lbl.pack(side="right", padx=10)

    def _build_storage_section(self):
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="x", padx=10, pady=8)
        frame.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="📁 Локальное хранилище",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=3, padx=16, pady=(12, 10), sticky="w")

        # DEST_DIR
        dest_lbl = ctk.CTkLabel(
            frame,
            text="Папка для архива (DEST_DIR):",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        dest_lbl.grid(row=1, column=0, padx=16, pady=6, sticky="w")

        self.dest_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Например: D:\\ или C:\\PhotosBackup",
            height=36,
        )
        self.dest_entry.grid(row=1, column=1, padx=(0, 10), pady=6, sticky="ew")

        browse_btn = ctk.CTkButton(
            frame,
            text="Обзор...",
            width=90,
            height=36,
            command=self._on_browse_dest_dir,
        )
        browse_btn.grid(row=1, column=2, padx=(0, 16), pady=6)

    def _build_cloud_safety_section(self):
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="x", padx=10, pady=8)
        frame.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="🛡️ Политика облака и безопасность удаления",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=3, padx=16, pady=(12, 10), sticky="w")

        # DAYS_TO_KEEP_IN_CLOUD
        days_title = ctk.CTkLabel(
            frame,
            text="Хранить в облаке (дней):",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        days_title.grid(row=1, column=0, padx=16, pady=6, sticky="w")

        slider_box = ctk.CTkFrame(frame, fg_color="transparent")
        slider_box.grid(row=1, column=1, columnspan=2, padx=(0, 16), pady=6, sticky="ew")
        slider_box.grid_columnconfigure(0, weight=1)

        self.days_slider = ctk.CTkSlider(
            slider_box,
            from_=0,
            to=730,
            number_of_steps=730,
            command=self._on_days_slider_change,
        )
        self.days_slider.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.days_val_lbl = ctk.CTkLabel(
            slider_box,
            text="180 дн.",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=65,
        )
        self.days_val_lbl.grid(row=0, column=1)

        self.cutoff_lbl = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        self.cutoff_lbl.grid(row=2, column=1, columnspan=2, padx=(0, 16), pady=(0, 8), sticky="w")

        # DRY_RUN_DELETE switch
        dry_lbl = ctk.CTkLabel(
            frame,
            text="Тестовый прогон (DRY_RUN):",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        dry_lbl.grid(row=3, column=0, padx=16, pady=6, sticky="w")

        self.dry_run_switch = ctk.CTkSwitch(
            frame,
            text="Включен (без реального удаления)",
            command=self._update_safety_badge,
        )
        self.dry_run_switch.grid(row=3, column=1, padx=(0, 16), pady=6, sticky="w")

        # ALLOW_CLOUD_DELETE switch
        allow_lbl = ctk.CTkLabel(
            frame,
            text="Разрешить удаление из облака:",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        allow_lbl.grid(row=4, column=0, padx=16, pady=6, sticky="w")

        self.allow_delete_switch = ctk.CTkSwitch(
            frame,
            text="ALLOW_CLOUD_DELETE",
            command=self._update_safety_badge,
        )
        self.allow_delete_switch.grid(row=4, column=1, padx=(0, 16), pady=6, sticky="w")

        # Safety badge banner
        self.safety_badge = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8,
            padx=14,
            pady=8,
            anchor="w",
        )
        self.safety_badge.grid(row=5, column=0, columnspan=3, padx=16, pady=(8, 14), sticky="ew")

    def _build_run_params_section(self):
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="x", padx=10, pady=8)
        frame.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="⚙️ Параметры выполнения",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 10), sticky="w")

        # STOP_AT_DATE
        stop_lbl = ctk.CTkLabel(
            frame,
            text="Остановиться на дате (STOP_AT_DATE):",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        stop_lbl.grid(row=1, column=0, padx=16, pady=6, sticky="w")

        stop_box = ctk.CTkFrame(frame, fg_color="transparent")
        stop_box.grid(row=1, column=1, padx=(0, 16), pady=6, sticky="ew")
        stop_box.grid_columnconfigure(0, weight=1)

        self.stop_date_entry = ctk.CTkEntry(
            stop_box,
            placeholder_text="Формат YYYY-MM-DD или оставьте пустым",
            height=36,
        )
        self.stop_date_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        clear_btn = ctk.CTkButton(
            stop_box,
            text="Очистить",
            width=80,
            height=36,
            fg_color=("gray75", "gray30"),
            command=lambda: self.stop_date_entry.delete(0, "end"),
        )
        clear_btn.grid(row=0, column=1)

        # MAX_DELETE_BLOCKS_PER_RUN
        max_del_lbl = ctk.CTkLabel(
            frame,
            text="Лимит блоков на удаление (0 = без лимита):",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        max_del_lbl.grid(row=2, column=0, padx=16, pady=6, sticky="w")

        self.max_delete_entry = ctk.CTkEntry(frame, height=36)
        self.max_delete_entry.grid(row=2, column=1, padx=(0, 16), pady=6, sticky="w")

        # LOG_LEVEL
        log_lvl_lbl = ctk.CTkLabel(
            frame,
            text="Уровень логирования (LOG_LEVEL):",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        log_lvl_lbl.grid(row=3, column=0, padx=16, pady=6, sticky="w")

        self.log_level_seg = ctk.CTkSegmentedButton(
            frame,
            values=["WARNING", "INFO", "DEBUG"],
        )
        self.log_level_seg.grid(row=3, column=1, padx=(0, 16), pady=6, sticky="w")

        # HEADLESS_MODE
        headless_lbl = ctk.CTkLabel(
            frame,
            text="Фоновый режим браузера (HEADLESS):",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        headless_lbl.grid(row=4, column=0, padx=16, pady=6, sticky="w")

        self.headless_switch = ctk.CTkSwitch(
            frame,
            text="HEADLESS (Рекомендуется False для React DOM)",
        )
        self.headless_switch.grid(row=4, column=1, padx=(0, 16), pady=6, sticky="w")

    def _build_advanced_section(self):
        self.adv_frame = ctk.CTkFrame(self, corner_radius=12)
        self.adv_frame.pack(fill="x", padx=10, pady=8)
        self.adv_frame.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            self.adv_frame,
            text="🔧 Дополнительные тайминги и прокрутка",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 10), sticky="w")

        # SCROLL_STEP_PIXELS
        scroll_lbl = ctk.CTkLabel(self.adv_frame, text="Шаг прокрутки (px):", font=ctk.CTkFont(size=13))
        scroll_lbl.grid(row=1, column=0, padx=16, pady=4, sticky="w")
        self.scroll_step_entry = ctk.CTkEntry(self.adv_frame, height=32, width=150)
        self.scroll_step_entry.grid(row=1, column=1, padx=(0, 16), pady=4, sticky="w")

        # SCROLL_WAIT_MS
        wait_lbl = ctk.CTkLabel(self.adv_frame, text="Пауза прокрутки (мс):", font=ctk.CTkFont(size=13))
        wait_lbl.grid(row=2, column=0, padx=16, pady=4, sticky="w")
        self.scroll_wait_entry = ctk.CTkEntry(self.adv_frame, height=32, width=150)
        self.scroll_wait_entry.grid(row=2, column=1, padx=(0, 16), pady=4, sticky="w")

        # DOWNLOAD_TIMEOUT_MS
        dl_timeout_lbl = ctk.CTkLabel(self.adv_frame, text="Таймаут скачивания (мс):", font=ctk.CTkFont(size=13))
        dl_timeout_lbl.grid(row=3, column=0, padx=16, pady=4, sticky="w")
        self.dl_timeout_entry = ctk.CTkEntry(self.adv_frame, height=32, width=150)
        self.dl_timeout_entry.grid(row=3, column=1, padx=(0, 16), pady=4, sticky="w")

        # DOWNLOAD_MAX_RETRIES
        retries_lbl = ctk.CTkLabel(self.adv_frame, text="Повторы скачивания:", font=ctk.CTkFont(size=13))
        retries_lbl.grid(row=4, column=0, padx=16, pady=4, sticky="w")
        self.retries_entry = ctk.CTkEntry(self.adv_frame, height=32, width=150)
        self.retries_entry.grid(row=4, column=1, padx=(0, 16), pady=4, sticky="w")

        # AUTH_WAIT_TIMEOUT_MS
        auth_timeout_lbl = ctk.CTkLabel(self.adv_frame, text="Таймаут входа 2FA (мс):", font=ctk.CTkFont(size=13))
        auth_timeout_lbl.grid(row=5, column=0, padx=16, pady=(4, 12), sticky="w")
        self.auth_timeout_entry = ctk.CTkEntry(self.adv_frame, height=32, width=150)
        self.auth_timeout_entry.grid(row=5, column=1, padx=(0, 16), pady=(4, 12), sticky="w")

    def _build_action_buttons(self):
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=10, pady=(15, 25))

        save_btn = ctk.CTkButton(
            btn_bar,
            text="💾 Сохранить настройки",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=42,
            fg_color=("#16a34a", "#22c55e"),
            hover_color=("#15803d", "#16a34a"),
            command=self.save_settings,
        )
        save_btn.pack(side="left", padx=(0, 10))

        reset_btn = ctk.CTkButton(
            btn_bar,
            text="🔄 Сбросить к сохраненным",
            font=ctk.CTkFont(size=13),
            height=42,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self.load_settings,
        )
        reset_btn.pack(side="left", padx=10)

        defaults_btn = ctk.CTkButton(
            btn_bar,
            text="Сброс к умолчанию",
            font=ctk.CTkFont(size=13),
            height=42,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self._restore_defaults,
        )
        defaults_btn.pack(side="left", padx=10)

        open_file_btn = ctk.CTkButton(
            btn_bar,
            text="📄 Открыть config.json",
            font=ctk.CTkFont(size=13),
            height=42,
            fg_color="transparent",
            text_color=("#2563eb", "#60a5fa"),
            hover=False,
            command=self._open_config_file,
        )
        open_file_btn.pack(side="right")

    def _on_browse_dest_dir(self):
        current_dir = self.dest_entry.get().strip() or "D:\\"
        folder = filedialog.askdirectory(
            title="Выберите папку для сохранения архива Google Photos",
            initialdir=current_dir if os.path.exists(current_dir) else None,
        )
        if folder:
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, os.path.normpath(folder))

    def _on_days_slider_change(self, val):
        days = int(val)
        self.days_val_lbl.configure(text=f"{days} дн.")
        cutoff_date = date.today() - timedelta(days=days)
        self.cutoff_lbl.configure(
            text=f"📅 Фото старше этой даты подлежат удалению: {cutoff_date.strftime('%d.%m.%Y')}"
        )

    def _update_safety_badge(self):
        dry_run = bool(self.dry_run_switch.get())
        allow_delete = bool(self.allow_delete_switch.get())

        if dry_run:
            self.safety_badge.configure(
                text="🛡️ БЕЗОПАСНЫЙ РЕЖИМ: Фото будут скачаны и верифицированы. Удаление из облака НЕ выполняется.",
                fg_color=("#dcfce7", "#14532d"),
                text_color=("#166534", "#86efac"),
            )
        elif not allow_delete:
            self.safety_badge.configure(
                text="ℹ️ УДАЛЕНИЕ ОТКЛЮЧЕНО: Удаление из облака заблокировано флагом ALLOW_CLOUD_DELETE.",
                fg_color=("#e0f2fe", "#075985"),
                text_color=("#0369a1", "#7dd3fc"),
            )
        else:
            self.safety_badge.configure(
                text="⚠️ ВНИМАНИЕ: Включено РЕАЛЬНОЕ удаление фото из Google Photos старше порога дней!",
                fg_color=("#fee2e2", "#7f1d1d"),
                text_color=("#b91c1c", "#fca5a5"),
            )

    def _populate_fields(self, cfg: dict):
        self.dest_entry.delete(0, "end")
        self.dest_entry.insert(0, cfg.get("DEST_DIR", "D:\\"))

        days = int(cfg.get("DAYS_TO_KEEP_IN_CLOUD", 180))
        self.days_slider.set(days)
        self._on_days_slider_change(days)

        if cfg.get("DRY_RUN_DELETE", True):
            self.dry_run_switch.select()
        else:
            self.dry_run_switch.deselect()

        if cfg.get("ALLOW_CLOUD_DELETE", True):
            self.allow_delete_switch.select()
        else:
            self.allow_delete_switch.deselect()

        self.stop_date_entry.delete(0, "end")
        self.stop_date_entry.insert(0, cfg.get("STOP_AT_DATE", ""))

        self.max_delete_entry.delete(0, "end")
        self.max_delete_entry.insert(0, str(cfg.get("MAX_DELETE_BLOCKS_PER_RUN", 0)))

        self.log_level_seg.set(str(cfg.get("LOG_LEVEL", "WARNING")).upper())

        if cfg.get("HEADLESS_MODE", False):
            self.headless_switch.select()
        else:
            self.headless_switch.deselect()

        self.scroll_step_entry.delete(0, "end")
        self.scroll_step_entry.insert(0, str(cfg.get("SCROLL_STEP_PIXELS", 500)))

        self.scroll_wait_entry.delete(0, "end")
        self.scroll_wait_entry.insert(0, str(cfg.get("SCROLL_WAIT_MS", 1500)))

        self.dl_timeout_entry.delete(0, "end")
        self.dl_timeout_entry.insert(0, str(cfg.get("DOWNLOAD_TIMEOUT_MS", 120000)))

        self.retries_entry.delete(0, "end")
        self.retries_entry.insert(0, str(cfg.get("DOWNLOAD_MAX_RETRIES", 3)))

        self.auth_timeout_entry.delete(0, "end")
        self.auth_timeout_entry.insert(0, str(cfg.get("AUTH_WAIT_TIMEOUT_MS", 300000)))

        self._update_safety_badge()

    def load_settings(self):
        cfg = load_config()
        self._populate_fields(cfg)
        self._show_notify("Настройки загружены", is_error=False)

    def _restore_defaults(self):
        if messagebox.askyesno("Сброс настроек", "Восстановить настройки по умолчанию?"):
            self._populate_fields(DEFAULT_CONFIG)
            self._show_notify("Восстановлены значения по умолчанию (не сохранены)", is_error=False)

    def collect_form_data(self) -> dict:
        cfg = load_config()
        cfg["DEST_DIR"] = self.dest_entry.get().strip()
        cfg["DAYS_TO_KEEP_IN_CLOUD"] = int(self.days_slider.get())
        cfg["DRY_RUN_DELETE"] = bool(self.dry_run_switch.get())
        cfg["ALLOW_CLOUD_DELETE"] = bool(self.allow_delete_switch.get())
        cfg["STOP_AT_DATE"] = self.stop_date_entry.get().strip()

        cfg["MAX_DELETE_BLOCKS_PER_RUN"] = self.max_delete_entry.get().strip() or "0"
        cfg["LOG_LEVEL"] = self.log_level_seg.get()
        cfg["HEADLESS_MODE"] = bool(self.headless_switch.get())

        cfg["SCROLL_STEP_PIXELS"] = self.scroll_step_entry.get().strip() or "500"
        cfg["SCROLL_WAIT_MS"] = self.scroll_wait_entry.get().strip() or "1500"
        cfg["DOWNLOAD_TIMEOUT_MS"] = self.dl_timeout_entry.get().strip() or "120000"
        cfg["DOWNLOAD_MAX_RETRIES"] = self.retries_entry.get().strip() or "3"
        cfg["AUTH_WAIT_TIMEOUT_MS"] = self.auth_timeout_entry.get().strip() or "300000"

        return cfg

    def save_settings(self):
        data = self.collect_form_data()
        is_valid, error = validate_config(data)
        if not is_valid:
            messagebox.showerror("Ошибка валидации", error)
            self._show_notify(f"❌ {error}", is_error=True)
            return

        # Convert validated numeric fields to int before saving
        data["MAX_DELETE_BLOCKS_PER_RUN"] = int(data["MAX_DELETE_BLOCKS_PER_RUN"])
        data["SCROLL_STEP_PIXELS"] = int(data["SCROLL_STEP_PIXELS"])
        data["SCROLL_WAIT_MS"] = int(data["SCROLL_WAIT_MS"])
        data["DOWNLOAD_TIMEOUT_MS"] = int(data["DOWNLOAD_TIMEOUT_MS"])
        data["DOWNLOAD_MAX_RETRIES"] = int(data["DOWNLOAD_MAX_RETRIES"])
        data["AUTH_WAIT_TIMEOUT_MS"] = int(data["AUTH_WAIT_TIMEOUT_MS"])

        # Confirmation modal if user turns off DRY_RUN and turns on ALLOW_CLOUD_DELETE
        if not data["DRY_RUN_DELETE"] and data["ALLOW_CLOUD_DELETE"]:
            confirm = messagebox.askyesno(
                "Подтверждение удаления",
                "ВНИМАНИЕ!\n\nВы отключаете безопасный режим (DRY_RUN_DELETE=false).\n"
                "При синхронизации бот будет НАВСЕГДА удалять фотографии из Google Photos в корзину!\n\n"
                "Вы уверены, что хотите сохранить эту конфигурацию?",
                icon="warning",
            )
            if not confirm:
                return

        try:
            save_config(data)
            self._show_notify("✅ Настройки успешно сохранены!", is_error=False)
            self.app.dashboard_view.refresh_metrics()
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))
            self._show_notify(f"❌ Ошибка сохранения: {e}", is_error=True)

    def _show_notify(self, text: str, is_error: bool = False):
        self.notify_lbl.configure(
            text=text,
            text_color=("#b91c1c", "#f87171") if is_error else ("#16a34a", "#4ade80"),
        )
        self.after(4000, lambda: self.notify_lbl.configure(text=""))

    def _open_config_file(self):
        if os.path.exists(CONFIG_PATH):
            os.startfile(CONFIG_PATH)
        else:
            messagebox.showinfo("Файл не найден", f"{CONFIG_PATH} еще не создан.")
