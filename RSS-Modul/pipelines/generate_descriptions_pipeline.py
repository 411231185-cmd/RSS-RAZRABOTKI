"""
Пайплайн генерации AI-описаний и опционального добавления SERVICESBLOCK.

Логика выбора товаров:
    По умолчанию обрабатываются только товары БЕЗ существующего сгенерированного
    текста (поведение «дополни недостающее»). Это безопасное умолчание для
    повторных запусков — генерация идёт только там, где её ещё не было.

Идемпотентность SERVICESBLOCK:
    Перед вставкой блока проверяется наличие уникального маркера
    SERVICESBLOCK_MARKER в тексте. Если маркер уже найден — вставка
    пропускается. Это гарантирует, что после N повторных запусков
    SERVICESBLOCK будет в тексте ровно один раз.
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from core.models import GeneratedText
from core.servicesblock import SERVICESBLOCK, SERVICESBLOCK_MARKER
from storage.db import init_db
from storage.repositories import (
    ProductRepository,
    SourceDescriptionRepository,
    GeneratedTextRepository,
)
from clients.llm_client import LLMClientRouter

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = Path("configs/ai/prompts/description_generic.md")
DEFAULT_TEXT_TYPE = "newdescriptiontop"

_product_repo = ProductRepository()
_src_desc_repo = SourceDescriptionRepository()
_gen_repo = GeneratedTextRepository()


def _load_prompt_template() -> str:
    """
    Прочитать шаблон промта из файла.

    Шаблон содержит плейсхолдеры в формате {code}, {name}, {application},
    {raw_description} — они подставляются через str.format() в _build_prompt.
    """
    if not PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Шаблон промта не найден: {PROMPT_TEMPLATE_PATH}. "
            f"Создай файл по образцу из описания спринта."
        )
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _build_prompt(template: str, product, raw_description: Optional[str]) -> str:
    """
    Подставить данные товара в шаблон промта.

    Если какое-то поле отсутствует — подставляем строку «не указано»,
    а не None. Это нужно, чтобы промт читался естественно и LLM
    не получал слово «None» в техническом тексте.
    """
    return template.format(
        code=product.code,
        name=product.name or "не указано",
        application=product.application or "не указано",
        raw_description=raw_description or "не указано",
    )


def _attach_services_block(content: str, add: bool) -> Tuple[str, bool]:
    """
    Решить, нужно ли добавлять SERVICESBLOCK, и при необходимости добавить.

    Возвращает кортеж (итоговый_текст, has_services_block_flag).

    Логика:
    - add=False             → возвращаем текст как есть, флаг False.
    - add=True, маркер есть → возвращаем текст как есть, флаг True.
    - add=True, маркера нет → добавляем блок и возвращаем флаг True.
    """
    if not add:
        return content, False

    if SERVICESBLOCK_MARKER in content:
        logger.debug(
            "SERVICESBLOCK уже присутствует в тексте — пропуск вставки (защита от дублей)"
        )
        return content, True

    return content + "\n\n" + SERVICESBLOCK, True


def generate_descriptions(
    model_id: str = "anthropic:claude-haiku-4.5",
    code_prefix: Optional[str] = None,
    add_services_block: bool = False,
) -> Dict[str, Any]:
    """
    Сгенерировать AI-описания и (опционально) добавить SERVICESBLOCK.

    Args:
        model_id:
            Идентификатор модели (через роутер: anthropic:..., openai:..., stub:...).
        code_prefix:
            Обрабатывать только товары с этим префиксом кода (startswith).
        add_services_block:
            Если True — после генерации к каждому описанию добавляется
            SERVICESBLOCK с защитой от дублирования через SERVICESBLOCK_MARKER.

    Returns:
        Словарь со статистикой выполнения.
    """
    logger.info(
        "Старт генерации | model_id=%s | code_prefix=%s | add_services_block=%s",
        model_id,
        code_prefix,
        add_services_block,
    )

    init_db()

    # Шаг 1. Найти товары без сгенерированного текста нужного типа.
    codes = _gen_repo.get_codes_without_generated(DEFAULT_TEXT_TYPE)
    logger.info(
        "Найдено %d товаров без описания типа '%s'",
        len(codes),
        DEFAULT_TEXT_TYPE,
    )

    # Шаг 2. Фильтр по префиксу.
    if code_prefix:
        before = len(codes)
        codes = [c for c in codes if c.startswith(code_prefix)]
        logger.info(
            "После фильтра по префиксу '%s': %d/%d",
            code_prefix,
            len(codes),
            before,
        )

    if not codes:
        logger.info("Нет товаров для генерации — все описания актуальны")
        return {
            "model_id": model_id,
            "code_prefix": code_prefix,
            "add_services_block": add_services_block,
            "items_processed": 0,
            "skipped": 0,
        }

    # Шаг 3. Собрать пары (product, prompt).
    template = _load_prompt_template()
    pairs = []
    skipped = 0

    for code in codes:
        product = _product_repo.get_by_code(code)
        if product is None:
            logger.warning("Товар с кодом '%s' отсутствует в БД — пропуск", code)
            skipped += 1
            continue

        src_descs = _src_desc_repo.get_by_code(code)
        raw_desc = next(
            (sd.raw_description for sd in src_descs if sd.raw_description),
            None,
        )

        pairs.append((product, _build_prompt(template, product, raw_desc)))

    if not pairs:
        logger.warning("Нет валидных пар (product, prompt) — нечего отправлять в API")
        return {
            "model_id": model_id,
            "code_prefix": code_prefix,
            "add_services_block": add_services_block,
            "items_processed": 0,
            "skipped": skipped,
        }

    # Шаг 4. Вызов LLM через роутер.
    logger.info(
        "Запуск генерации для %d товаров (model_id=%s)",
        len(pairs),
        model_id,
    )
    client = LLMClientRouter(model_id=model_id)
    prompts = [p for _, p in pairs]

    results = []
    for prompt in prompts:
        content = client.generate_description(prompt)
        results.append(content)

    # Шаг 5. Сохранение результатов.
    items_processed = 0
    errors = 0

    for (product, _), content in zip(pairs, results):
        try:
            final_content, has_sb = _attach_services_block(
                content,
                add_services_block,
            )
            _gen_repo.upsert(
                GeneratedText(
                    code=product.code,
                    text_type=DEFAULT_TEXT_TYPE,
                    content=final_content,
                    model_id=model_id,
                    has_services_block=has_sb,
                )
            )
            items_processed += 1
        except Exception as e:
            logger.exception("Ошибка обработки code='%s': %s", product.code, e)
            errors += 1

    stats: Dict[str, Any] = {
        "model_id": model_id,
        "code_prefix": code_prefix,
        "add_services_block": add_services_block,
        "items_processed": items_processed,
        "skipped": skipped + errors,
    }
    logger.info("Генерация завершена: %s", stats)
    return stats