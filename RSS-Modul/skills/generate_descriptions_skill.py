import logging
from typing import Optional
from pipelines.generate_descriptions_pipeline import generate_descriptions

logger = logging.getLogger(__name__)


def skill_generate_descriptions(
    model_id: str = "claude-sonnet-4-20250514",
    code_prefix: Optional[str] = None,
    add_services_block: bool = True,
    force_regenerate: bool = False,
) -> dict:
    """Сгенерировать AI-описания для товаров без описания."""
    logger.info(
        f"skill_generate_descriptions: prefix={code_prefix}, "
        f"add_sb={add_services_block}, force={force_regenerate}"
    )
    return generate_descriptions(
        code_prefix=code_prefix,
        model_id=model_id,
        add_services_block=add_services_block,
        force_regenerate=force_regenerate,
    )
