"""
Пайплайн экспорта сгенерированных описаний обратно в формат PromPortal XLSX.

Цепочка:
    БД (generated_texts) → словарь {code: text} → writer → output XLSX

Учёт SERVICESBLOCK:
- Если в БД у записи has_services_block=1 — текст уже содержит блок, не дублируем.
- Если has_services_block=0 и пользователь передал add_services_block=True — добавляем.
- Маркер SERVICESBLOCK_MARKER служит финальной защитой от дублей в самом тексте.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from core.servicesblock import SERVICESBLOCK, SERVICESBLOCK_MARKER
from storage.db import init_db, get_connection
from adapters.promportal_export_writer import write_promportal_xlsx

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = Path("input/PromPortal №1.xlsx")
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_TEXT_TYPE = "newdescriptiontop"


def _load_descriptions_from_db(
    text_type: str,
    code_prefix: Optional[str],
    add_services_block: bool,
) -> Dict[str, str]:
    """
    Прочитать {code: content} из generated_texts, опционально присоединив SERVICESBLOCK.

    Защита от дублирования блока:
    1. Если has_services_block=1 → текст уже с блоком, добавлять нельзя.
    2. Если SERVICESBLOCK_MARKER уже в content → блок есть, добавлять нельзя.
    3. Иначе и только если add_services_block=True → добавляем.
    """
    sql = "SELECT code, content, has_services_block FROM generated_texts WHERE text_type = ?"
    params: list = [text_type]
    if code_prefix:
        sql += " AND code LIKE ?"
        params.append(f"{code_prefix}%")

    result: Dict[str, str] = {}
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    for row in rows:
        code = row["code"]
        content = row["content"] or ""
        has_sb = bool(row["has_services_block"])

        if add_services_block and not has_sb and SERVICESBLOCK_MARKER not in content:
            content = content + "\n\n" + SERVICESBLOCK

        result[code] = content

    logger.info("Из БД загружено %d описаний (text_type=%s)", len(result), text_type)
    return result


def export_promportal(
    template_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    code_prefix: Optional[str] = None,
    add_services_block: bool = False,
    text_type: str = DEFAULT_TEXT_TYPE,
) -> Dict[str, Any]:
    """
    Экспортировать сгенерированные описания обратно в формат PromPortal XLSX.

    Args:
        template_path:      исходный PromPortal XLSX-шаблон. По умолчанию input/PromPortal №1.xlsx.
        output_path:        куда сохранить. По умолчанию output/promportal_export_YYYYMMDD_HHMMSS.xlsx.
        code_prefix:        фильтр по префиксу кода (для тестов на подмножестве).
        add_services_block: добавлять SERVICESBLOCK к описаниям, у которых его ещё нет.
        text_type:          какой тип сгенерированного текста брать.

    Returns:
        {"output": str, "total": N, "updated": N, "missing": N, "skipped_no_code": N}
    """
    init_db()

    template = template_path or DEFAULT_TEMPLATE
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"promportal_export_{ts}.xlsx"

    logger.info(
        "Старт экспорта | template=%s | output=%s | prefix=%s | add_sb=%s",
        template, output_path, code_prefix, add_services_block,
    )

    descriptions = _load_descriptions_from_db(
        text_type=text_type,
        code_prefix=code_prefix,
        add_services_block=add_services_block,
    )

    if not descriptions:
        logger.warning("В БД нет описаний для экспорта (фильтр prefix=%s)", code_prefix)

    write_stats = write_promportal_xlsx(
        template_path=template,
        output_path=output_path,
        descriptions_by_code=descriptions,
    )

    return {
        "output": str(output_path),
        "loaded_from_db": len(descriptions),
        **write_stats,
    }