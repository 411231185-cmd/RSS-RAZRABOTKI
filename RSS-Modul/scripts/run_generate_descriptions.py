#!/usr/bin/env python3
"""
CLI-скрипт для запуска генерации AI-описаний.

Запуск:
    python -m scripts.run_generate_descriptions
    python -m scripts.run_generate_descriptions --code-prefix 163
    python -m scripts.run_generate_descriptions --code-prefix 163 --add-services-block
    python -m scripts.run_generate_descriptions --model-id claude-sonnet -v

По умолчанию работает в "режиме пропусков": генерирует описания только
для товаров, у которых их ещё нет. Это безопасное поведение для повторных
запусков — повторный прогон не перезаписывает существующие данные.
"""
import argparse
import logging
import sys
from typing import Optional

from pipelines.generate_descriptions_pipeline import generate_descriptions


def setup_logging(verbose: bool) -> None:
    """
    Настройка logging — идентична той, что в run_collect_raw.py.

    Дублирование функции здесь — осознанное решение: каждый скрипт
    самодостаточен и не зависит от вспомогательных модулей. Если позже
    функций станет много, можно будет вынести их в общий модуль
    scripts/_common.py — но не раньше.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RSS-Modul: генерация AI-описаний с опциональным SERVICESBLOCK",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model-id",
        default="claude-sonnet",
        help="Идентификатор модели Claude",
    )
    parser.add_argument(
        "--code-prefix",
        default=None,
        help="Обрабатывать только товары с кодом, начинающимся на этот префикс",
    )
    parser.add_argument(
        "--add-services-block",
        action="store_true",
        help=(
            "Добавить SERVICESBLOCK в конец каждого описания. "
            "Защищено от дублирования через маркер — повторные запуски безопасны."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробное логирование (уровень DEBUG)",
    )
    return parser.parse_args(argv)


def main() -> int:
    """
    Точка входа. Возвращает 0 при успехе, 1 при ошибке.
    """
    args = parse_args()
    setup_logging(args.verbose)

    log = logging.getLogger("run_generate_descriptions")

    log.info("=" * 60)
    log.info(
        "Запуск генерации | model_id=%s | code_prefix=%s | add_services_block=%s",
        args.model_id,
        args.code_prefix or "<все>",
        args.add_services_block,
    )
    log.info("=" * 60)

    try:
        stats = generate_descriptions(
            model_id=args.model_id,
            code_prefix=args.code_prefix,
            add_services_block=args.add_services_block,
        )
    except FileNotFoundError as e:
        # Самая частая причина — отсутствует файл шаблона промта.
        log.error("Файл не найден: %s", e)
        return 1
    except Exception as e:
        log.exception("Неожиданная ошибка: %s", e)
        return 1

    print()
    print("✅ Генерация завершена")
    print(f"   Модель:                {stats['model_id']}")
    print(f"   Префикс кода:          {stats['code_prefix'] or '<все>'}")
    print(f"   SERVICESBLOCK:         {'добавлен' if stats['add_services_block'] else 'не добавлен'}")
    print(f"   Товаров обработано:    {stats['items_processed']}")
    print(f"   Пропущено:             {stats['skipped']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())