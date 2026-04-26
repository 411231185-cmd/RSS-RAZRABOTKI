#!/usr/bin/env python3
"""
CLI-скрипт для запуска сбора сырых данных из источника.

Запуск:
    python -m scripts.run_collect_raw --source promportal_export
    python -m scripts.run_collect_raw --source promportal_export --code-prefix 163
    python -m scripts.run_collect_raw --source promportal_export --file "input/PromPortal №1.xlsx"
    python -m scripts.run_collect_raw --source promportal_export -v

Скрипт — тонкий слой над пайплайном. Его единственные обязанности:
1) распарсить CLI-аргументы;
2) настроить logging.basicConfig (без core.logging_config и без YAML);
3) вызвать collect_raw_from_source с явно переданными параметрами;
4) напечатать сводку и вернуть код выхода.

Никакой бизнес-логики здесь быть не должно.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from pipelines.collect_raw_pipeline import collect_raw_from_source

# Дефолтные пути к файлам для каждого источника.
# Вынесено в словарь, чтобы при добавлении нового источника не лезть
# в саму функцию main(). Имя ключа совпадает с тем, что приходит в --source.
DEFAULT_FILES = {
    "promportal_export": Path("input/PromPortal №1.xlsx"),
}


def setup_logging(verbose: bool) -> None:
    """
    Настроить стандартный logging без зависимости от core.logging_config.

    При verbose=True уровень DEBUG (видно всё, включая внутренние операции БД).
    По умолчанию INFO — только важные сообщения.

    Формат включает время, уровень и имя логгера. Имя логгера показывает,
    какой именно модуль выдал сообщение — полезно для отладки.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    """
    Парсинг CLI-аргументов.

    Вынесен в отдельную функцию, чтобы:
    1) main() оставался тонким и читабельным;
    2) можно было тестировать парсинг отдельно (например, в unit-тесте
       вызвать parse_args(["--source", "promportal_export", "-v"])).
    """
    parser = argparse.ArgumentParser(
        description="RSS-Modul: сбор сырых данных из источников в мастер-БД",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=list(DEFAULT_FILES.keys()),
        help="Идентификатор источника (определяет используемый адаптер)",
    )
    parser.add_argument(
        "--code-prefix",
        default=None,
        help="Обрабатывать только товары с кодом, начинающимся на этот префикс",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Путь к файлу источника. Если не задан — используется DEFAULT_FILES",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробное логирование (уровень DEBUG)",
    )
    return parser.parse_args(argv)


def main() -> int:
    """
    Точка входа.

    Возвращаемое значение — код выхода процесса:
        0 — успех;
        1 — ошибка любого рода.
    Возврат кода критичен для интеграции с cron/CI: bash и cron реагируют
    именно на код возврата, а не на текст вывода.
    """
    args = parse_args()
    setup_logging(args.verbose)

    log = logging.getLogger("run_collect_raw")

    # Определяем путь к файлу: либо явный из --file, либо дефолтный
    # из словаря DEFAULT_FILES. Превращаем в str, потому что наша
    # функция пайплайна принимает str (соответственно ТЗ).
    file_path: Path = Path(args.file) if args.file else DEFAULT_FILES[args.source]
    file_path_str = str(file_path)

    log.info("=" * 60)
    log.info("Запуск сбора | source=%s | file=%s", args.source, file_path_str)
    log.info("=" * 60)

    # Главный try/except защищает только от ошибок верхнего уровня.
    # Конкретные ошибки (FileNotFoundError, ValueError) обрабатываются
    # отдельно, чтобы давать пользователю понятное сообщение, а не
    # сырой traceback.
    try:
        stats = collect_raw_from_source(
            source=args.source,
            code_prefix=args.code_prefix,
            file_path=file_path_str,
        )
    except FileNotFoundError as e:
        log.error("Файл не найден: %s", e)
        return 1
    except ValueError as e:
        log.error("Ошибка в параметрах: %s", e)
        return 1
    except Exception as e:
        # Для непредвиденных ошибок — полный traceback в лог.
        log.exception("Неожиданная ошибка: %s", e)
        return 1

    # Финальная сводка печатается всегда, даже без -v.
    # Это пользовательский вывод, а не лог — поэтому через print, а не через logger.
    print()
    print("✅ Сбор завершён успешно")
    print(f"   Источник:             {stats['source']}")
    print(f"   Файл:                 {stats['file_path']}")
    print(f"   Товаров записано:     {stats['products']}")
    print(f"   Описаний записано:    {stats['descriptions']}")
    print(f"   Пропущено по фильтру: {stats['skipped']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())