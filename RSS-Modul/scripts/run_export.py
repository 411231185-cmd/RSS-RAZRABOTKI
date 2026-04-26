#!/usr/bin/env python3
"""
CLI для экспорта описаний обратно в PromPortal XLSX.

Запуск:
    python -m scripts.run_export
    python -m scripts.run_export --code-prefix 163
    python -m scripts.run_export --add-services-block
    python -m scripts.run_export --template "input/PromPortal №1.xlsx" --output "output/result.xlsx"
"""
import argparse
import logging
import sys
from pathlib import Path

from pipelines.export_pipeline import export_promportal


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RSS-Modul: экспорт описаний из БД обратно в PromPortal XLSX",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--template", default=None, help="Путь к исходному XLSX-шаблону")
    parser.add_argument("--output", default=None, help="Путь к выходному XLSX")
    parser.add_argument("--code-prefix", default=None, help="Фильтр по префиксу кода")
    parser.add_argument("--add-services-block", action="store_true",
                        help="Добавить SERVICESBLOCK к описаниям без него")
    parser.add_argument("--verbose", "-v", action="store_true", help="DEBUG-логирование")
    args = parser.parse_args()

    setup_logging(args.verbose)
    log = logging.getLogger("run_export")

    log.info("=" * 60)
    log.info("Запуск экспорта PromPortal | prefix=%s | add_sb=%s",
             args.code_prefix or "<все>", args.add_services_block)
    log.info("=" * 60)

    try:
        stats = export_promportal(
            template_path=Path(args.template) if args.template else None,
            output_path=Path(args.output) if args.output else None,
            code_prefix=args.code_prefix,
            add_services_block=args.add_services_block,
        )
    except FileNotFoundError as e:
        log.error("Файл не найден: %s", e)
        return 1
    except ValueError as e:
        log.error("Ошибка структуры шаблона: %s", e)
        return 1
    except Exception as e:
        log.exception("Неожиданная ошибка: %s", e)
        return 1

    print()
    print("✅ Экспорт завершён")
    print(f"   Выходной файл:        {stats['output']}")
    print(f"   Загружено из БД:      {stats['loaded_from_db']}")
    print(f"   Всего строк в файле:  {stats['total']}")
    print(f"   Обновлено описаний:   {stats['updated']}")
    print(f"   Без нового описания:  {stats['missing']}")
    print(f"   Пропущено без кода:   {stats['skipped_no_code']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())