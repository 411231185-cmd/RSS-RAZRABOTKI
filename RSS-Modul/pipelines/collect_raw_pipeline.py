from core.config import get_settings
from core.logging_config import get_logger

logger = get_logger(__name__)


def collect_raw_from_source(source: str, code_prefix: str | None = None) -> None:
    """
    Flow A: заглушка пайплайна сбора сырых описаний.
    Здесь Клод допишет вызовы адаптеров и сохранение в БД.
    """
    settings = get_settings()
    logger.info("collect_raw_from_source start: source=%s, code_prefix=%s", source, code_prefix)
    logger.info("using data_dir=%s", settings.get_path("data_dir"))
    # TODO: adapters + storage
    logger.info("collect_raw_from_source finished (stub)")
