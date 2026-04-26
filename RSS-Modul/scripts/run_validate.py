#!/usr/bin/env python3
"""
CLI для валидации сгенерированных описаний.

Запуск:
    python -m scripts.run_validate
    python -m scripts.run_validate --code-prefix 163
    python -m scripts.run_validate --code-prefix 163 --only-invalid -v
"""
import argparse
import logging
import sys

from pipelines.validate_pipeline import validate_descriptions, fetch_invalid


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RSS-Modul: валидация сгенерированных описаний",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--text-type", default="newdescriptiontop")
    parser.add_argument("--code-prefix", default=None)
    parser.add_argument("--only-invalid", action="store_true",
                        help="Вывести список кодов с ошибками")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    log = logging.getLogger("run_validate")

    log.info("=" * 60)
    log.info("Запуск валидации | text_type=%s | prefix=%s",
             args.text_type, args.code_prefix or "<все>")
    log.info("=" * 60)

    try:
        stats = validate_descriptions(
            text_type=args.text_type,
            code_prefix=args.code_prefix,
        )
    except FileNotFoundError as e:
        log.error("Файл не найден: %s", e)
        return 1
    except Exception as e:
        log.exception("Неожиданная ошибка: %s", e)
        return 1

    print()
    print("✅ Валидация завершена")
    print(f"   Проверено:    {stats['checked']}")
    print(f"   Валидно:      {stats['valid']}")
    print(f"   С ошибками:   {stats['invalid']}")

    if args.only_invalid and stats["invalid"] > 0:
        invalid = fetch_invalid(args.text_type, args.code_prefix)
        print()
        print(f"--- Невалидные записи ({len(invalid)}) ---")
        for item in invalid:
            errors_str = "; ".join(item["errors"]) if item["errors"] else "<нет деталей>"
            print(f"  [{item['code']}] {errors_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())