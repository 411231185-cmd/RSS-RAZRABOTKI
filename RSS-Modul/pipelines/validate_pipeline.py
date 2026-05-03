"""
Пайплайн валидации сгенерированных описаний.

Проверки (в соответствии с эталонным промтом):
- запрещённая лексика (маркетинг, призывы, "мы/наш");
- выдуманные числовые параметры (числа есть в описании, но отсутствуют во входных данных);
- длина 4–6 предложений;
- отсутствие HTML, списков, кавычек вокруг текста, вводных фраз.

Результаты пишутся в таблицу validation_results через UPSERT по (code, text_type).
"""
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from core.text_utils import (
    FORBIDDEN_MARKETING,
    FORBIDDEN_FIRST_PERSON,
    FORBIDDEN_CTA,
    FORBIDDEN_INTROS,
    has_html_garbage,
    has_marketing_cliche,
)
from storage.db import init_db, get_connection

logger = logging.getLogger(__name__)

VALIDATION_SCHEMA_PATH = Path("storage/schema_validation.sql")

# -- Выдуманные параметры ----------------------------------------------------
# Если в описании встречаются конкретные технические числа,
# а во входных данных raw_description/name/application таких чисел нет — это флаг.
NUMERIC_CLAIM_PATTERNS = [
    (r"модул[ьеяю]\s*[=:]?\s*\d+[\.,]?\d*", "модуль"),
    (r"числ[оаел]+\s+зубь?ев\s*[=:]?\s*\d+",  "число зубьев"),
    (r"\bz\s*=\s*\d+",                         "число зубьев (z)"),
    (r"\bm\s*=\s*\d+[\.,]?\d*",                "модуль (m)"),
    (r"диаметр[а-я]*\s*[=:]?\s*\d+[\.,]?\d*",  "диаметр"),
    (r"шаг[а-я]*\s*[=:]?\s*\d+[\.,]?\d*",      "шаг"),
    (r"твёрдост[ьи]\s+(hrc|hb)\s*\d+",         "твёрдость"),
    (r"hrc\s*\d+",                              "твёрдость HRC"),
    (r"\d+\s*мм",                               "размер в мм"),
]


def _ensure_validation_table() -> None:
    """Создать таблицу валидации, если её ещё нет."""
    if not VALIDATION_SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Схема валидации не найдена: {VALIDATION_SCHEMA_PATH}")
    with get_connection() as conn:
        conn.executescript(VALIDATION_SCHEMA_PATH.read_text(encoding="utf-8"))


def _count_sentences(text: str) -> int:
    """Подсчёт предложений по терминальной пунктуации (с учётом многоточий)."""
    cleaned = re.sub(r"\.{3,}", ".", text)
    sentences = re.findall(r"[^.!?]+[.!?]", cleaned)
    return len(sentences)


def _has_forbidden(text: str, patterns: List[str]) -> List[str]:
    """Вернуть список найденных запрещённых фрагментов."""
    found = []
    lower = text.lower()
    for pat in patterns:
        m = re.search(pat, lower, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            found.append(m.group(0).strip())
    return found


def _extract_numbers(text: str) -> set:
    """Извлечь все числовые значения из текста для сравнения."""
    if not text:
        return set()
    nums = re.findall(r"\d+[\.,]?\d*", text)
    return {n.replace(",", ".") for n in nums}


def _check_invented_numbers(content: str, source_text: str) -> List[str]:
    """
    Найти технические числовые утверждения в content, отсутствующие в source_text.
    Возвращает список названий категорий (модуль, диаметр и т.п.).
    """
    source_numbers = _extract_numbers(source_text)
    invented: List[str] = []
    for pattern, label in NUMERIC_CLAIM_PATTERNS:
        m = re.search(pattern, content, flags=re.IGNORECASE)
        if not m:
            continue
        # Извлечь число из найденного фрагмента и проверить, есть ли оно в источнике.
        nums_in_match = _extract_numbers(m.group(0))
        if nums_in_match and not (nums_in_match & source_numbers):
            invented.append(f"{label}: '{m.group(0).strip()}'")
    return invented


def _validate_text(content: str, source_text: str) -> Tuple[bool, List[str]]:
    """Полная валидация одного описания. Возвращает (is_valid, errors)."""
    errors: List[str] = []

    if not content or not content.strip():
        return False, ["пустое описание"]

    stripped = content.strip()

    # 1. HTML-мусор (теги или сущности) — после очистки в адаптере означает мусор от Claude
    from core.servicesblock import SERVICESBLOCK_MARKER
    text_wo_block = stripped.split(SERVICESBLOCK_MARKER)[0]
    if has_html_garbage(text_wo_block):
        errors.append("HTML_GARBAGE: содержит HTML-теги или сущности")

    # 2. Кавычки вокруг всего текста
    if (stripped.startswith('"') and stripped.endswith('"')) or \
       (stripped.startswith("«") and stripped.endswith("»")):
        errors.append("текст обёрнут в кавычки")

    # 3. Списки/маркеры
    if re.search(r"^\s*[-*•]\s", stripped, flags=re.MULTILINE):
        errors.append("содержит маркированный список")
    if re.search(r"^\s*\d+[.)]\s", stripped, flags=re.MULTILINE):
        errors.append("содержит нумерованный список")

    # 4. Запрещённая лексика
    marketing = _has_forbidden(stripped, FORBIDDEN_MARKETING)
    if marketing:
        errors.append(f"маркетинг: {', '.join(marketing)}")
    first_person = _has_forbidden(stripped, FORBIDDEN_FIRST_PERSON)
    if first_person:
        errors.append(f"от первого лица: {', '.join(first_person)}")
    cta = _has_forbidden(stripped, FORBIDDEN_CTA)
    if cta:
        errors.append(f"призывы к действию: {', '.join(cta)}")
    intros = _has_forbidden(stripped, FORBIDDEN_INTROS)
    if intros:
        errors.append(f"вводные фразы: {', '.join(intros)}")

    # 7. Маркетинговые клише ("лучшая цена", "высокое качество" и т.п.)
    if has_marketing_cliche(stripped):
        errors.append("MARKETING_TONE_CLICHE: маркетинговые клише")

    # 5. Длина 4–6 предложений
    n_sent = _count_sentences(stripped)
    if n_sent < 4:
        errors.append(f"мало предложений: {n_sent} (нужно 4–6)")
    elif n_sent > 6:
        errors.append(f"много предложений: {n_sent} (нужно 4–6)")

    # 6. Выдуманные числовые параметры
    invented = _check_invented_numbers(stripped, source_text)
    if invented:
        errors.append(f"возможно выдуманные параметры: {'; '.join(invented)}")

    return (len(errors) == 0), errors


def _load_records_for_validation(
    text_type: str,
    code_prefix: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Загрузить из БД записи для валидации: content + объединённый source-текст
    (raw_description + name + application) для проверки выдуманных чисел.
    """
    sql = """
        SELECT
            gt.code         AS code,
            gt.content      AS content,
            p.name          AS name,
            p.application   AS application,
            COALESCE(GROUP_CONCAT(sd.raw_description, ' '), '') AS raw_descriptions
        FROM generated_texts gt
        JOIN products p ON p.code = gt.code
        LEFT JOIN source_descriptions sd ON sd.code = gt.code
        WHERE gt.text_type = ?
    """
    params: list = [text_type]
    if code_prefix:
        sql += " AND gt.code LIKE ?"
        params.append(f"{code_prefix}%")
    sql += " GROUP BY gt.code, gt.content, p.name, p.application"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def validate_descriptions(
    text_type: str = "newdescriptiontop",
    code_prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Провалидировать описания и записать результат в validation_results.

    Returns:
        {"checked": N, "valid": N, "invalid": N}
    """
    init_db()
    _ensure_validation_table()

    logger.info("Старт валидации | text_type=%s | code_prefix=%s", text_type, code_prefix)
    records = _load_records_for_validation(text_type, code_prefix)
    logger.info("Загружено %d записей для проверки", len(records))

    if not records:
        return {"checked": 0, "valid": 0, "invalid": 0}

    upsert_sql = """
        INSERT INTO validation_results (code, text_type, is_valid, errors, checked_at)
        VALUES (:code, :text_type, :is_valid, :errors, datetime('now'))
        ON CONFLICT(code, text_type) DO UPDATE SET
            is_valid   = excluded.is_valid,
            errors     = excluded.errors,
            checked_at = excluded.checked_at
    """

    valid_count = 0
    invalid_count = 0

    with get_connection() as conn:
        for rec in records:
            source_text = " ".join(filter(None, [
                rec.get("name"), rec.get("application"), rec.get("raw_descriptions"),
            ]))
            is_valid, errors = _validate_text(rec["content"] or "", source_text)
            conn.execute(upsert_sql, {
                "code": rec["code"],
                "text_type": text_type,
                "is_valid": int(is_valid),
                "errors": json.dumps(errors, ensure_ascii=False) if errors else None,
            })
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                logger.debug("INVALID code=%s | %s", rec["code"], errors)

    stats = {"checked": len(records), "valid": valid_count, "invalid": invalid_count}
    logger.info("Валидация завершена: %s", stats)
    return stats


def fetch_invalid(text_type: str, code_prefix: Optional[str]) -> List[Dict[str, Any]]:
    """Вернуть список невалидных записей для отчёта."""
    sql = """
        SELECT code, errors FROM validation_results
        WHERE text_type = ? AND is_valid = 0
    """
    params: list = [text_type]
    if code_prefix:
        sql += " AND code LIKE ?"
        params.append(f"{code_prefix}%")
    sql += " ORDER BY code"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{"code": r["code"], "errors": json.loads(r["errors"]) if r["errors"] else []}
            for r in rows]