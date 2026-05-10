import argparse
import json
import os
import sys
from collections import Counter
from datetime import date, datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = {
    "STATE_FILE": "backup_manifest.json",
    "DAYS_TO_KEEP_IN_CLOUD": 180,
}


def configure_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def resolve_path(path):
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(config_path):
    if not os.path.exists(config_path):
        return DEFAULT_CONFIG.copy()

    config = DEFAULT_CONFIG.copy()
    config.update(load_json(config_path))
    return config


def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_cli_date(value):
    parsed = parse_date(value)
    if not parsed:
        raise argparse.ArgumentTypeError("Дата должна быть в формате YYYY-MM-DD")
    return parsed


def format_size(size):
    if size is None:
        return "0 Б"
    value = float(size)
    for unit in ["Б", "КБ", "МБ", "ГБ", "ТБ"]:
        if value < 1024 or unit == "ТБ":
            if unit == "Б":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} ТБ"


def bool_text(value):
    return "да" if value else "нет"


def short_text(value, max_len=96):
    text = " ".join(str(value or "").split())
    if len(text) <= max_len:
        return text
    return f"{text[:max_len - 1]}…"


def block_age_days(entry, as_of):
    photo_date = parse_date(entry.get("photo_date"))
    if not photo_date:
        return None
    return (as_of - photo_date).days


def is_delete_candidate(entry, as_of, days_to_keep):
    age = block_age_days(entry, as_of)
    return (
        age is not None
        and age > days_to_keep
        and bool(entry.get("files_verified"))
        and not bool(entry.get("deleted_from_cloud"))
    )


def is_covered_by_group_action(manifest, entry, as_of, days_to_keep):
    covering_block_id = entry.get("covered_by_block_id")
    if not covering_block_id:
        return False

    covering_block = manifest.get("blocks", {}).get(covering_block_id)
    if not covering_block:
        return False

    return bool(covering_block.get("deleted_from_cloud")) or is_delete_candidate(covering_block, as_of, days_to_keep)


def is_effective_delete_candidate(manifest, entry, as_of, days_to_keep):
    return is_delete_candidate(entry, as_of, days_to_keep) and not is_covered_by_group_action(
        manifest, entry, as_of, days_to_keep
    )


def is_delete_blocked(entry, as_of, days_to_keep):
    age = block_age_days(entry, as_of)
    return (
        age is not None
        and age > days_to_keep
        and not bool(entry.get("files_verified"))
        and not bool(entry.get("deleted_from_cloud"))
    )


def iter_blocks(manifest):
    for block_id, entry in manifest.get("blocks", {}).items():
        yield block_id, entry


def collect_summary(manifest, manifest_path, as_of, days_to_keep):
    blocks = list(iter_blocks(manifest))
    covered_dates = manifest.get("covered_dates", {})
    dates = [parse_date(entry.get("photo_date")) for _, entry in blocks]
    dates = [item for item in dates if item]
    files_count = sum(len(entry.get("files") or []) for _, entry in blocks)
    manifest_size = os.path.getsize(manifest_path) if os.path.exists(manifest_path) else 0

    stats_size = 0
    for _, entry in blocks:
        download_stats = entry.get("download_stats") or {}
        stats_size += int(download_stats.get("size") or 0)

    raw_delete_candidates = [
        (block_id, entry) for block_id, entry in blocks if is_delete_candidate(entry, as_of, days_to_keep)
    ]
    effective_delete_candidates = [
        (block_id, entry)
        for block_id, entry in raw_delete_candidates
        if is_effective_delete_candidate(manifest, entry, as_of, days_to_keep)
    ]

    return {
        "manifest_path": manifest_path,
        "manifest_size": manifest_size,
        "version": manifest.get("version"),
        "blocks_count": len(blocks),
        "covered_dates_count": len(covered_dates),
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "type_counts": Counter(entry.get("block_type") or "unknown" for _, entry in blocks),
        "verified_count": sum(1 for _, entry in blocks if entry.get("files_verified")),
        "unverified_count": sum(1 for _, entry in blocks if not entry.get("files_verified")),
        "deleted_count": sum(1 for _, entry in blocks if entry.get("deleted_from_cloud")),
        "errors_count": sum(1 for _, entry in blocks if entry.get("last_error")),
        "delete_candidates_count": len(effective_delete_candidates),
        "raw_delete_candidates_count": len(raw_delete_candidates),
        "covered_delete_candidates_count": len(raw_delete_candidates) - len(effective_delete_candidates),
        "delete_blocked_count": sum(1 for _, entry in blocks if is_delete_blocked(entry, as_of, days_to_keep)),
        "files_count": files_count,
        "stats_size": stats_size,
    }


def print_summary(summary, as_of, days_to_keep):
    print("Сводка manifest")
    print(f"  Файл: {summary['manifest_path']}")
    print(f"  Размер manifest: {format_size(summary['manifest_size'])}")
    print(f"  Версия: {summary['version']}")
    print(f"  Дата отчета: {as_of.isoformat()}")
    print(f"  DAYS_TO_KEEP_IN_CLOUD: {days_to_keep}")
    print()
    print("Состояние")
    print(f"  Блоков всего: {summary['blocks_count']}")
    print(f"  Подтверждено: {summary['verified_count']}")
    print(f"  Не подтверждено: {summary['unverified_count']}")
    print(f"  Удалено из облака: {summary['deleted_count']}")
    print(f"  Покрытых дат группами: {summary['covered_dates_count']}")
    print(f"  Файловых записей в manifest: {summary['files_count']}")
    print(f"  Объем по download_stats: {format_size(summary['stats_size'])}")
    print()
    print("Контроль")
    print(f"  Диапазон дат: {summary['date_min'] or '-'} — {summary['date_max'] or '-'}")
    print(f"  Кандидатов на удаление без дублей: {summary['delete_candidates_count']}")
    print(f"  Покрытых группами item-кандидатов: {summary['covered_delete_candidates_count']}")
    print(f"  Сырых candidate-записей всего: {summary['raw_delete_candidates_count']}")
    print(f"  Старых, но неподтвержденных: {summary['delete_blocked_count']}")
    print(f"  Блоков с ошибками: {summary['errors_count']}")
    print()
    print("Типы блоков")
    for block_type, count in sorted(summary["type_counts"].items()):
        print(f"  {block_type}: {count}")


def sorted_entries(entries):
    def sort_key(item):
        block_id, entry = item
        return (
            entry.get("photo_date") or "9999-99-99",
            entry.get("block_type") or "",
            entry.get("label") or "",
            block_id,
        )

    return sorted(entries, key=sort_key)


def print_entries(title, entries, manifest, as_of, days_to_keep, limit):
    entries = sorted_entries(entries)
    print(title)
    print(f"  Найдено: {len(entries)}")
    if not entries:
        return

    shown = entries[:limit]
    for block_id, entry in shown:
        age = block_age_days(entry, as_of)
        age_text = f"{age} дн." if age is not None else "возраст неизвестен"
        files = entry.get("files") or []
        status = "deleted" if entry.get("deleted_from_cloud") else "active"
        verified = "verified" if entry.get("files_verified") else "unverified"
        if is_effective_delete_candidate(manifest, entry, as_of, days_to_keep):
            candidate = "delete-candidate"
        elif is_covered_by_group_action(manifest, entry, as_of, days_to_keep):
            candidate = "covered-by-group"
        elif is_delete_candidate(entry, as_of, days_to_keep):
            candidate = "raw-delete-candidate"
        else:
            candidate = "keep"
        print()
        print(f"  {entry.get('photo_date') or '-'} | {age_text} | {entry.get('block_type') or 'unknown'} | {verified} | {status} | {candidate}")
        print(f"  id: {block_id}")
        print(f"  label: {short_text(entry.get('label'))}")
        if entry.get("verification_source"):
            print(f"  verification_source: {entry.get('verification_source')}")
        if entry.get("covered_by_block_id"):
            print(f"  covered_by_block_id: {entry.get('covered_by_block_id')}")
        if entry.get("download_stats"):
            stats = entry["download_stats"]
            print(
                "  download_stats: "
                f"processed={stats.get('processed', 0)}, "
                f"new={stats.get('new', 0)}, "
                f"size={format_size(stats.get('size', 0))}"
            )
        if entry.get("last_error"):
            print(f"  last_error: {entry.get('last_error')}")
        if files:
            names = [item.get("name") or os.path.basename(item.get("path") or "") for item in files]
            print(f"  files: {', '.join(short_text(name, 48) for name in names[:8])}")
            if len(names) > 8:
                print(f"  files_more: {len(names) - 8}")

    if len(entries) > limit:
        print()
        print(f"  Показано {limit} из {len(entries)}. Увеличь --limit, если нужно больше.")


def print_date_report(manifest, target_date, as_of, days_to_keep, limit):
    date_key = target_date.isoformat()
    coverage = manifest.get("covered_dates", {}).get(date_key)
    entries = [(block_id, entry) for block_id, entry in iter_blocks(manifest) if entry.get("photo_date") == date_key]

    print(f"Дата {date_key}")
    print(f"  Блоков: {len(entries)}")
    print(f"  Покрыта группой: {bool_text(bool(coverage and coverage.get('files_verified')))}")
    if coverage:
        print(f"  covering_block_id: {coverage.get('covering_block_id')}")
        print(f"  files_count: {coverage.get('files_count', 0)}")
        print(f"  verified_at: {coverage.get('verified_at') or '-'}")
    print()
    print_entries("Блоки даты", entries, manifest, as_of, days_to_keep, limit)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Отчет по backup_manifest.json без запуска Google Photos bot."
    )
    parser.add_argument("--config", default=os.path.join(BASE_DIR, "config.json"), help="Путь к config.json")
    parser.add_argument("--manifest", help="Путь к backup_manifest.json. По умолчанию берется из config.json")
    parser.add_argument("--days-to-keep", type=int, help="Порог DAYS_TO_KEEP_IN_CLOUD для расчета кандидатов на удаление")
    parser.add_argument("--as-of", type=parse_cli_date, default=date.today(), help="Дата отчета YYYY-MM-DD")
    parser.add_argument("--date", type=parse_cli_date, action="append", help="Показать блоки конкретной даты YYYY-MM-DD")
    parser.add_argument("--unverified", action="store_true", help="Показать неподтвержденные блоки")
    parser.add_argument("--delete-candidates", action="store_true", help="Показать подтвержденные блоки старше порога")
    parser.add_argument(
        "--all-delete-candidates",
        action="store_true",
        help="Показать все candidate-записи, включая item-записи, покрытые группами",
    )
    parser.add_argument("--blocked-delete", action="store_true", help="Показать старые блоки, которые нельзя удалять без проверки")
    parser.add_argument("--errors", action="store_true", help="Показать блоки с last_error")
    parser.add_argument("--no-summary", action="store_true", help="Не печатать общую сводку")
    parser.add_argument("--limit", type=int, default=30, help="Максимум строк в списках")
    return parser


def main():
    configure_stdout()
    args = build_parser().parse_args()

    config_path = resolve_path(args.config)
    config = load_config(config_path)
    manifest_path = resolve_path(args.manifest or config.get("STATE_FILE", "backup_manifest.json"))
    days_to_keep = args.days_to_keep
    if days_to_keep is None:
        days_to_keep = int(config.get("DAYS_TO_KEEP_IN_CLOUD", 180))

    if not os.path.exists(manifest_path):
        raise SystemExit(f"Manifest не найден: {manifest_path}")

    manifest = load_json(manifest_path)
    summary = collect_summary(manifest, manifest_path, args.as_of, days_to_keep)

    printed_any = False
    if not args.no_summary:
        print_summary(summary, args.as_of, days_to_keep)
        printed_any = True

    if args.date:
        for target_date in args.date:
            if printed_any:
                print()
                print("-" * 72)
            print_date_report(manifest, target_date, args.as_of, days_to_keep, args.limit)
            printed_any = True

    if args.unverified:
        entries = [(block_id, entry) for block_id, entry in iter_blocks(manifest) if not entry.get("files_verified")]
        if printed_any:
            print()
            print("-" * 72)
        print_entries("Неподтвержденные блоки", entries, manifest, args.as_of, days_to_keep, args.limit)
        printed_any = True

    if args.delete_candidates:
        entries = [
            (block_id, entry)
            for block_id, entry in iter_blocks(manifest)
            if is_effective_delete_candidate(manifest, entry, args.as_of, days_to_keep)
        ]
        if printed_any:
            print()
            print("-" * 72)
        print_entries("Кандидаты на удаление из облака без дублей", entries, manifest, args.as_of, days_to_keep, args.limit)
        printed_any = True

    if args.all_delete_candidates:
        entries = [
            (block_id, entry)
            for block_id, entry in iter_blocks(manifest)
            if is_delete_candidate(entry, args.as_of, days_to_keep)
        ]
        if printed_any:
            print()
            print("-" * 72)
        print_entries("Все candidate-записи, включая покрытые группами", entries, manifest, args.as_of, days_to_keep, args.limit)
        printed_any = True

    if args.blocked_delete:
        entries = [(block_id, entry) for block_id, entry in iter_blocks(manifest) if is_delete_blocked(entry, args.as_of, days_to_keep)]
        if printed_any:
            print()
            print("-" * 72)
        print_entries("Старые блоки без подтверждения архива", entries, manifest, args.as_of, days_to_keep, args.limit)
        printed_any = True

    if args.errors:
        entries = [(block_id, entry) for block_id, entry in iter_blocks(manifest) if entry.get("last_error")]
        if printed_any:
            print()
            print("-" * 72)
        print_entries("Блоки с ошибками", entries, manifest, args.as_of, days_to_keep, args.limit)


if __name__ == "__main__":
    main()
