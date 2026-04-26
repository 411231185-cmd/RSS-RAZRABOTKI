import logging
from pathlib import Path
from typing import Optional
from pipelines.collect_raw_pipeline import collect_raw_from_source

logger = logging.getLogger(__name__)

DEFAULT_FILE = Path("input/PromPortal №1.xlsx")


def skill_collect_raw_promportal(
    file_path: Optional[str] = None,
    code_prefix: Optional[str] = None,
) -> dict:
    """Собрать сырые данные из файла экспорта PromPortal."""
    path = Path(file_path) if file_path else DEFAULT_FILE
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    logger.info(f"skill_collect_raw_promportal: file={path}, prefix={code_prefix}")
    return collect_raw_from_source("promportal_export", path, code_prefix)
