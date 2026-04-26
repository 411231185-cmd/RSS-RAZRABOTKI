import logging
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from core.models import Product, SourceDescription

logger = logging.getLogger(__name__)

SOURCE_NAME = "promportal_export"

# Имена столбцов в файле PromPortal.
# Подогнал под твой пример: "Наименование" вместо "Название".
COL_CODE        = "Код товара"
COL_NAME        = "Наименование"
COL_DESC        = "Описание"
COL_APPLICATION = "Применение"
COL_PRICE       = "Цена"


def load_promportal_export(
    file_path: Path,
) -> Tuple[List[Product], List[SourceDescription]]:
    """
    Прочитать PromPortal XLSX и вернуть (products, source_descriptions).

    Коды нормализуются: str.strip() — чтобы пробелы не сломали JOIN.
    Строки с пустым/отсутствующим кодом отбрасываются с предупреждением.
    """
    logger.info(f"Reading PromPortal export: {file_path}")

    try:
        # Явно указываем движок, чтобы не было ошибки
        df = pd.read_excel(file_path, dtype=str, engine="openpyxl")
    except Exception as e:
        logger.error(f"Cannot read {file_path}: {e}")
        raise

    logger.info(f"Loaded {len(df)} rows. Columns: {list(df.columns)}")

    if COL_CODE not in df.columns:
        raise ValueError(
            f"Столбец '{COL_CODE}' не найден в {file_path.name}. "
            f"Доступные столбцы: {list(df.columns)}"
        )

    # Нормализуем коды
    df[COL_CODE] = df[COL_CODE].astype(str).str.strip()

    mask_valid = df[COL_CODE].notna() & (df[COL_CODE] != "") & (df[COL_CODE] != "nan")
    dropped = (~mask_valid).sum()
    if dropped:
        logger.warning(f"Dropped {dropped} rows with missing/invalid '{COL_CODE}'")
    df = df[mask_valid].copy()

    products: List[Product] = []
    source_descriptions: List[SourceDescription] = []

    for _, row in df.iterrows():
        code = row[COL_CODE]

        price = None
        if COL_PRICE in df.columns:
            try:
                price_str = str(row[COL_PRICE]).strip().replace(" ", "")
                price = float(price_str.replace(",", "."))
            except (ValueError, AttributeError):
                price = None

        products.append(
            Product(
                code=code,
                name=str(row.get(COL_NAME, "")).strip(),
                application=str(row.get(COL_APPLICATION, "")).strip() or None,
                price=price,
                source_file=file_path.name,
            )
        )

        raw_desc = str(row.get(COL_DESC, "")).strip()
        source_descriptions.append(
            SourceDescription(
                code=code,
                source=SOURCE_NAME,
                raw_description=raw_desc or None,
            )
        )

    with_desc = sum(1 for sd in source_descriptions if sd.raw_description)
    logger.info(f"Parsed: {len(products)} products, {with_desc} with descriptions")

    return products, source_descriptions