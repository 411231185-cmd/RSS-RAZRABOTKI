import logging
from typing import Any, Dict
from skills.collect_raw_skill import skill_collect_raw_promportal
from skills.generate_descriptions_skill import skill_generate_descriptions

logger = logging.getLogger(__name__)

TASK_MAP = {
    "collect_raw_promportal":  skill_collect_raw_promportal,
    "generate_descriptions":   skill_generate_descriptions,
}


def run_task(task_id: str, **kwargs) -> Dict[str, Any]:
    if task_id not in TASK_MAP:
        raise ValueError(
            f"Неизвестный task_id: '{task_id}'. "
            f"Доступные задачи: {list(TASK_MAP.keys())}"
        )
    logger.info(f"run_task: {task_id} | params={kwargs}")
    result = TASK_MAP[task_id](**kwargs)
    logger.info(f"run_task complete: {task_id} → {result}")
    return result
