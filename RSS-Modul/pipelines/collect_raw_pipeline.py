"""
Пайплайн сбора сырых данных из источников в мастер-БД.

Тонкая прослойка-оркестратор:
    источник (XLSX/CSV) → адаптер → нормализованные модели → репозитории → SQLite

Зачем «тонкая»?
    Бизнес-логика чтения файла лежит в адаптерах (adapters/*).
    Логика записи в БД лежит в репозиториях (storage/repositories.py).
    Этот файл только связывает два мира: говорит «прочитай вот этот файл вот
    этим адаптером и положи результат в мастер-БД». Никаких трансформаций
    данных здесь нет — это упрощает тестирование и понимание.

Идемпотентность:
    обеспечена на уровне схемы БД (UNIQUE(code, source) + ON CONFLICT DO UPDATE).
    Повторный запуск с теми же входными данными перезаписывает существующие
    записи, а не создаёт дубликаты.

Главный инвариант:
    поле `code` (Код товара) никогда не модифицируется на этом уровне.
    Используется как единственный ключ связки между всеми источниками.
"""
import logging
import importlib
from pathlib import Path
from typing import Optional, Dict, Any

# Импорты из самого проекта — это нормально и нужно.
# Запрещены только core.config, core.logging_config и yaml.
from storage.db import init_db
from storage.repositories import ProductRepository, SourceDescriptionRepository

# Логгер берётся через стандартный logging. Имя совпадает с именем модуля —
# это позволяет при необходимости настроить разный уровень детализации
# для разных модулей через logging.getLogger("pipelines.collect_raw_pipeline").
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Реестр адаптеров.
#
# Ключ — идентификатор источника (то же значение, что приходит в --source).
# Значение — строка вида "module.path:function_name", позволяющая
# импортировать адаптер лениво (только когда он реально нужен).
#
# Зачем ленивая загрузка?
#   1. Если у тебя пять адаптеров, и при импорте пайплайна Python грузит
#      их все, то ошибка в одном (например, отсутствующая зависимость
#      pandas в одном из адаптеров) ломает работу всех остальных.
#   2. Добавление нового адаптера не требует редактирования секции
#      импортов сверху файла — достаточно одной новой строки в словаре.
# ---------------------------------------------------------------------------
ADAPTER_REGISTRY: Dict[str, str] = {
    "promportal_export": "adapters.promportal_export_adapter:load_promportal_export",
}

# Репозитории создаются один раз на уровне модуля.
# Они stateless — внутри каждого метода открывается своё соединение с БД
# и закрывается после использования. Поэтому повторное использование
# одного экземпляра безопасно и эффективно (не плодим лишние объекты).
_product_repo = ProductRepository()
_source_desc_repo = SourceDescriptionRepository()


def _resolve_adapter(source: str):
    """
    Найти и импортировать функцию-адаптер по имени источника.

    Использует динамический импорт через importlib, чтобы:
    - не загружать все адаптеры при импорте этого модуля (lazy loading);
    - избежать потенциальных циклических импортов.
    """
    if source not in ADAPTER_REGISTRY:
        available = ", ".join(ADAPTER_REGISTRY.keys()) or "<пусто>"
        raise ValueError(
            f"Неизвестный источник: '{source}'. "
            f"Доступные источники: {available}. "
            f"Чтобы добавить новый — зарегистрируй адаптер в ADAPTER_REGISTRY."
        )

    module_path, func_name = ADAPTER_REGISTRY[source].split(":")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def collect_raw_from_source(
    source: str,
    code_prefix: Optional[str] = None,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Прочитать данные из файла источника и записать их в мастер-БД.

    Args:
        source:
            Идентификатор источника. Должен присутствовать в ADAPTER_REGISTRY.
            Пример: "promportal_export".
        code_prefix:
            Если задан, обрабатываются только товары с кодом, начинающимся
            на этот префикс. Фильтрация типа «код начинается с» (str.startswith).
            Удобно для отладки на подмножестве данных.
        file_path:
            Путь к файлу источника. Принимается как str для совместимости
            с CLI-аргументами; внутри функции преобразуется в pathlib.Path.

    Returns:
        Словарь со статистикой обработки. Структура и набор ключей
        соответствуют требованиям ТЗ.
    """
    logger.info(
        "Старт сбора | source=%s | code_prefix=%s | file_path=%s",
        source, code_prefix, file_path,
    )

    # Преобразуем file_path в Path только если он задан.
    # Если нет — значение остаётся None, и функция должна сама понять,
    # где брать файл (или упасть с понятной ошибкой).
    resolved_path: Optional[Path] = Path(file_path) if file_path else None

    # Заглушка для случая, когда file_path не передан.
    # Сейчас все известные источники требуют файл, но в будущем могут
    # появиться источники, читающие данные из API — там file_path не нужен.
    if resolved_path is None:
        raise ValueError(
            "Параметр file_path обязателен для текущих источников. "
            "Передай путь к XLSX/CSV-файлу через CLI-аргумент --file "
            "или подставь дефолтный путь в скрипте run_collect_raw.py."
        )

    if not resolved_path.exists():
        raise FileNotFoundError(f"Файл источника не найден: {resolved_path}")

    # Инициализация БД идемпотентна — таблицы создаются только если их нет.
    # Делаем это после проверок, чтобы не создавать пустую БД при заведомо
    # неуспешном запуске.
    init_db()

    # Шаг 1. Получить функцию-адаптер и прочитать файл.
    # Контракт адаптера: вернуть кортеж (List[Product], List[SourceDescription]).
    adapter_func = _resolve_adapter(source)
    products, source_descs = adapter_func(resolved_path)
    logger.info(
        "Адаптер вернул: %d товаров, %d сырых описаний",
        len(products), len(source_descs),
    )

    # Шаг 2. Применить фильтр по префиксу кода.
    # Делаем это здесь, а не в адаптере: задача адаптера — просто прочитать
    # файл целиком, ничего не зная о фильтрации. Это позволяет переиспользовать
    # адаптер в других контекстах (например, для полной выгрузки).
    skipped = 0
    if code_prefix:
        original_count = len(products)
        products = [p for p in products if p.code.startswith(code_prefix)]
        source_descs = [d for d in source_descs if d.code.startswith(code_prefix)]
        skipped = original_count - len(products)
        logger.info(
            "После фильтра по префиксу '%s': оставлено %d, пропущено %d",
            code_prefix, len(products), skipped,
        )

    # Шаг 3. Записать в БД, если есть что писать.
    # Пустой результат после фильтра — не ошибка, а валидный сценарий.
    if not products:
        logger.warning("После фильтрации не осталось ни одного товара для записи")
        return {
            "source": source,
            "code_prefix": code_prefix,
            "file_path": str(resolved_path),
            "products": 0,
            "descriptions": 0,
            "skipped": skipped,
        }

    # Сначала products — из-за внешнего ключа в source_descriptions.
    # Если попытаться записать описание раньше, FK-проверка упадёт.
    products_written = _product_repo.upsert_batch(products)

    # В таблицу source_descriptions пишем только непустые описания.
    # Хранить NULL под видом «сырого описания» бессмысленно и засоряет БД.
    non_empty_descs = [d for d in source_descs if d.raw_description]
    descs_written = (
        _source_desc_repo.upsert_batch(non_empty_descs) if non_empty_descs else 0
    )

    stats: Dict[str, Any] = {
        "source": source,
        "code_prefix": code_prefix,
        "file_path": str(resolved_path),
        "products": products_written,
        "descriptions": descs_written,
        "skipped": skipped,
    }
    logger.info("Сбор завершён: %s", stats)
    return stats