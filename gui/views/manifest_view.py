"""Manifest & Audit view for Google Photos Backup & Sync Bot.

Integrates backup_manifest.json inspection, summary analytics,
express integrity audit (from manifest_report.py), search and filtering.
"""

import os
from datetime import date
from tkinter import messagebox
import customtkinter as ctk

import manifest_report as mr
from gui.config_manager import load_config


class ManifestView(ctk.CTkFrame):
    """Manifest explorer and integrity audit screen."""

    def __init__(self, master, app_controller, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app_controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._all_entries = []
        self._manifest_cache = None

        self._build_header()
        self._build_summary_cards()
        self._build_filter_bar()
        self._build_content_area()

        self.reload_manifest()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Манифест и аудит целостности",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e")

        audit_btn = ctk.CTkButton(
            btn_box,
            text="🔍 Экспресс-аудит",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
            fg_color=("#2563eb", "#3b82f6"),
            hover_color=("#1d4ed8", "#2563eb"),
            command=self._run_express_audit,
        )
        audit_btn.pack(side="left", padx=4)

        open_dest_btn = ctk.CTkButton(
            btn_box,
            text="📂 Папка архива",
            font=ctk.CTkFont(size=13),
            height=36,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self._open_dest_folder,
        )
        open_dest_btn.pack(side="left", padx=4)

        reload_btn = ctk.CTkButton(
            btn_box,
            text="🔄 Обновить",
            font=ctk.CTkFont(size=13),
            height=36,
            width=80,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self.reload_manifest,
        )
        reload_btn.pack(side="left", padx=4)

    def _build_summary_cards(self):
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=20, pady=5)
        for i in range(5):
            cards.grid_columnconfigure(i, weight=1, uniform="kpi")

        self.lbl_blocks = self._create_card(cards, 0, "Всего блоков", "—")
        self.lbl_verified = self._create_card(cards, 1, "Подтверждено", "—")
        self.lbl_deleted = self._create_card(cards, 2, "Удалено из облака", "—")
        self.lbl_candidates = self._create_card(cards, 3, "Кандидаты удаления", "—")
        self.lbl_errors = self._create_card(cards, 4, "Ошибки", "—")

    def _create_card(self, parent, col, title, initial_val):
        frame = ctk.CTkFrame(parent, corner_radius=10)
        frame.grid(row=0, column=col, padx=4, pady=4, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        t_lbl = ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray70"),
        )
        t_lbl.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

        v_lbl = ctk.CTkLabel(
            frame,
            text=initial_val,
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        v_lbl.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")
        return v_lbl

    def _build_filter_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        bar.grid_columnconfigure(0, weight=1)

        # Search field
        self.search_entry = ctk.CTkEntry(
            bar,
            placeholder_text="Поиск по дате (например: 2024-05) или тексту...",
            height=36,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filters())

        # Status filter
        self.filter_option = ctk.CTkOptionMenu(
            bar,
            values=["Все блоки", "Подтвержденные", "Удаленные", "Кандидаты на удаление", "С ошибками", "Неподтвержденные"],
            height=36,
            command=lambda v: self._apply_filters(),
        )
        self.filter_option.grid(row=0, column=1, padx=(0, 10))

        # Counter of filtered items
        self.count_lbl = ctk.CTkLabel(
            bar,
            text="0 записей",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
        )
        self.count_lbl.grid(row=0, column=2, padx=5)

    def _build_content_area(self):
        self.table_frame = ctk.CTkScrollableFrame(self, corner_radius=12)
        self.table_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.table_frame.grid_columnconfigure(0, weight=1)

    def reload_manifest(self):
        cfg = load_config()
        state_file = cfg.get("STATE_FILE", "backup_manifest.json")
        resolved = mr.resolve_path(state_file)

        if not os.path.exists(resolved):
            self.lbl_blocks.configure(text="0")
            self.lbl_verified.configure(text="0")
            self.lbl_deleted.configure(text="0")
            self.lbl_candidates.configure(text="0")
            self.lbl_errors.configure(text="0")
            self._render_empty_message("Файл манифеста еще не создан. Он появится после первого запуска синхронизации.")
            return

        try:
            self._manifest_cache = mr.load_json(resolved)
            summary = mr.collect_summary(
                self._manifest_cache,
                resolved,
                mr.date.today(),
                cfg.get("DAYS_TO_KEEP_IN_CLOUD", 180),
            )

            self.lbl_blocks.configure(text=str(summary["blocks_count"]))
            self.lbl_verified.configure(text=str(summary["verified_count"]))
            self.lbl_deleted.configure(text=str(summary["deleted_count"]))
            self.lbl_candidates.configure(text=str(summary["delete_candidates_count"]))
            self.lbl_errors.configure(text=str(summary["errors_count"]))

            self._all_entries = mr.sorted_entries(mr.iter_blocks(self._manifest_cache))
            self._apply_filters()
        except Exception as e:
            self._render_empty_message(f"Ошибка чтения манифеста: {e}")

    def _render_empty_message(self, msg: str):
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        lbl = ctk.CTkLabel(
            self.table_frame,
            text=msg,
            font=ctk.CTkFont(size=14),
            text_color=("gray40", "gray70"),
        )
        lbl.pack(pady=40)

    def _apply_filters(self):
        if not self._all_entries:
            return

        query = self.search_entry.get().strip().lower()
        filter_mode = self.filter_option.get()
        cfg = load_config()
        as_of = date.today()
        days_to_keep = cfg.get("DAYS_TO_KEEP_IN_CLOUD", 180)

        filtered = []
        for block_id, entry in self._all_entries:
            label = str(entry.get("label") or "").lower()
            photo_date = str(entry.get("photo_date") or "").lower()
            bid = block_id.lower()

            if query and (query not in label and query not in photo_date and query not in bid):
                continue

            is_verified = bool(entry.get("files_verified"))
            is_deleted = bool(entry.get("deleted_from_cloud"))
            has_error = bool(entry.get("last_error"))
            is_candidate = mr.is_effective_delete_candidate(self._manifest_cache, entry, as_of, days_to_keep)

            if filter_mode == "Подтвержденные" and not is_verified:
                continue
            elif filter_mode == "Удаленные" and not is_deleted:
                continue
            elif filter_mode == "Кандидаты на удаление" and not is_candidate:
                continue
            elif filter_mode == "С ошибками" and not has_error:
                continue
            elif filter_mode == "Неподтвержденные" and is_verified:
                continue

            filtered.append((block_id, entry))

        self.count_lbl.configure(text=f"{len(filtered)} записей (показано до 100)")
        self._render_entries(filtered[:100])

    def _render_entries(self, entries):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        if not entries:
            self._render_empty_message("Записи, соответствующие выбранным фильтрам, не найдены.")
            return

        for idx, (block_id, entry) in enumerate(entries):
            row = ctk.CTkFrame(self.table_frame, corner_radius=8, height=44)
            row.pack(fill="x", padx=4, pady=3)
            row.grid_columnconfigure(1, weight=1)

            p_date = entry.get("photo_date") or "—"
            b_type = "Группа" if entry.get("block_type") == "group" else "Элемент"
            files_count = len(entry.get("files") or [])
            label = entry.get("label") or block_id

            # Date badge
            date_lbl = ctk.CTkLabel(
                row,
                text=p_date,
                font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                width=100,
                anchor="w",
            )
            date_lbl.grid(row=0, column=0, padx=(12, 8), pady=8)

            # Label / Details
            text_desc = f"[{b_type}] {mr.short_text(label, max_len=60)} ({files_count} ф.)"
            desc_lbl = ctk.CTkLabel(
                row,
                text=text_desc,
                font=ctk.CTkFont(size=12),
                anchor="w",
            )
            desc_lbl.grid(row=0, column=1, padx=4, pady=8, sticky="w")

            # Status pill
            status_text, bg_color, fg_color = self._get_status_pill(entry)
            pill = ctk.CTkLabel(
                row,
                text=status_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=bg_color,
                text_color=fg_color,
                corner_radius=6,
                padx=8,
                pady=4,
            )
            pill.grid(row=0, column=2, padx=8, pady=8)

            # Details action button
            info_btn = ctk.CTkButton(
                row,
                text="Инфо",
                width=55,
                height=28,
                font=ctk.CTkFont(size=11),
                command=lambda b=block_id, e=entry: self._show_block_details(b, e),
            )
            info_btn.grid(row=0, column=3, padx=(0, 10), pady=8)

    def _get_status_pill(self, entry: dict):
        if entry.get("last_error"):
            return "⚠️ Ошибка", ("#fee2e2", "#7f1d1d"), ("#b91c1c", "#fca5a5")
        if entry.get("deleted_from_cloud"):
            return "🗑️ Удален", ("#f3f4f6", "#374151"), ("#4b5563", "#9ca3af")
        if entry.get("files_verified"):
            return "✅ В архиве", ("#dcfce7", "#14532d"), ("#166534", "#86efac")
        return "⏳ Не проверен", ("#fef3c7", "#78350f"), ("#b45309", "#fcd34d")

    def _show_block_details(self, block_id: str, entry: dict):
        """Displays modal with full block info and file list."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Детали блока: {block_id}")
        dialog.geometry("700x500")
        dialog.transient(self)
        dialog.grab_set()

        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(
            dialog,
            text=f"Блок: {entry.get('label') or block_id}",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        header.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")

        textbox = ctk.CTkTextbox(dialog, font=ctk.CTkFont(family="Consolas", size=12))
        textbox.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="nsew")

        lines = [
            f"ID блока: {block_id}",
            f"Дата фото: {entry.get('photo_date')}",
            f"Тип: {entry.get('block_type')}",
            f"Верифицирован: {entry.get('files_verified')}",
            f"Удален из облака: {entry.get('deleted_from_cloud')}",
            f"Источник верификации: {entry.get('verification_source')}",
            f"Покрыт блоком: {entry.get('covered_by_block_id')}",
            f"Последняя ошибка: {entry.get('last_error') or 'нет'}",
            "",
            "--- ФАЙЛЫ В БЛОКЕ ---",
        ]
        files = entry.get("files") or []
        for f in files:
            lines.append(f"• {f.get('rel_path')} ({mr.format_size(f.get('size'))})")
            if f.get("sha256"):
                lines.append(f"  SHA-256: {f.get('sha256')}")

        textbox.insert("end", "\n".join(lines))
        textbox.configure(state="disabled")

        close_btn = ctk.CTkButton(dialog, text="Закрыть", command=dialog.destroy)
        close_btn.grid(row=2, column=0, pady=(0, 15))

    def _run_express_audit(self):
        """Runs audit from manifest_report and displays dialog."""
        cfg = load_config()
        state_file = cfg.get("STATE_FILE", "backup_manifest.json")
        resolved = mr.resolve_path(state_file)

        if not os.path.exists(resolved):
            messagebox.showinfo("Аудит манифеста", "Файл манифеста не найден.")
            return

        manifest = mr.load_json(resolved)
        as_of = date.today()
        days_to_keep = cfg.get("DAYS_TO_KEEP_IN_CLOUD", 180)
        summary = mr.collect_summary(manifest, resolved, as_of, days_to_keep)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Отчет экспресс-аудита целостности")
        dialog.geometry("750x550")
        dialog.transient(self)
        dialog.grab_set()

        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        title = ctk.CTkLabel(
            dialog,
            text="📊 Результаты экспресс-аудита манифеста",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        title.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")

        tb = ctk.CTkTextbox(dialog, font=ctk.CTkFont(family="Consolas", size=12))
        tb.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="nsew")

        report = [
            f"Файл манифеста: {summary['manifest_path']}",
            f"Размер файла: {mr.format_size(summary['manifest_size'])}",
            f"Версия схемы: {summary['version']}",
            f"Дата проверки: {as_of.isoformat()}",
            f"Порог хранения в облаке: {days_to_keep} дней",
            "=" * 60,
            "СТАТУС ЦЕЛОСТНОСТИ:",
            f"• Всего блоков: {summary['blocks_count']}",
            f"• Подтверждено локально: {summary['verified_count']}",
            f"• Не подтверждено: {summary['unverified_count']}",
            f"• Удалено из облака: {summary['deleted_count']}",
            f"• Покрытых дат группами: {summary['covered_dates_count']}",
            f"• Файловых записей: {summary['files_count']}",
            f"• Общий объем скачанного: {mr.format_size(summary['stats_size'])}",
            f"• Диапазон дат: {summary['date_min'] or '—'} — {summary['date_max'] or '—'}",
            "=" * 60,
            "БЕЗОПАСНОСТЬ УДАЛЕНИЯ И ОШИБКИ:",
            f"• Кандидатов на удаление без дублей: {summary['delete_candidates_count']}",
            f"• Покрытых группами item-кандидатов: {summary['covered_delete_candidates_count']}",
            f"• Блоков с ошибками: {summary['errors_count']}",
            f"• Старых, но неподтвержденных (удаление заблокировано): {summary['delete_blocked_count']}",
            "=" * 60,
        ]
        if summary["errors_count"] == 0 and summary["delete_blocked_count"] == 0:
            report.append("✅ Аудит пройден без замечаний! Нарушений безопасности не обнаружено.")
        else:
            report.append("⚠️ Обнаружены блоки, требующие внимания (см. подробности во вкладке Манифеста).")

        tb.insert("end", "\n".join(report))
        tb.configure(state="disabled")

        btn = ctk.CTkButton(dialog, text="Закрыть", command=dialog.destroy)
        btn.grid(row=2, column=0, pady=(0, 15))

    def _open_dest_folder(self):
        cfg = load_config()
        dest = cfg.get("DEST_DIR", "D:\\")
        if os.path.exists(dest):
            os.startfile(dest)
        else:
            messagebox.showinfo("Папка не найдена", f"Папка {dest} не существует.")
