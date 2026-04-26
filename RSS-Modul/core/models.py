from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Product:
    """Мастер-запись товара. Поле code — неприкосновенно."""
    code: str
    name: str
    application: Optional[str] = None   # Применение: «1М63, 16К20»
    price: Optional[float] = None       # read-only из источника
    source_file: Optional[str] = None   # имя файла-источника для трассировки


@dataclass
class SourceDescription:
    """Сырое описание из конкретного источника (PromPortal, Directus и т.д.)."""
    code: str
    source: str             # «promportal_export», «directus», «kristina_export»
    raw_description: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class GeneratedText:
    """AI-сгенерированное описание для товара."""
    code: str
    text_type: str          # «newdescriptiontop» — основной тип
    content: str
    model_id: str = "claude-sonnet-4-20250514"
    has_services_block: bool = False    # флаг: SERVICESBLOCK уже вставлен
    created_at: Optional[datetime] = None
