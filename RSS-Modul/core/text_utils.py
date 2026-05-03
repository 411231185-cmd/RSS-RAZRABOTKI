"""
Текстовые утилиты на чистом regex. Без сторонних NLP-зависимостей.
Используется в адаптерах (очистка raw_description) и в валидаторе.
"""
import re
from typing import List, Optional

# === Очистка ===
HTML_ENTITY_PATTERN = re.compile(r"&[a-zA-Z]+;|&#\d+;")
HTML_TAG_PATTERN = re.compile(r"<[a-zA-Z/!][^>]*>")
MULTISPACE_PATTERN = re.compile(r"\s+")

# === Идентификаторы ===
PHOTO_URL_PATTERN = re.compile(r"^https?://.*\.(jpg|jpeg|png|webp)(\?.*)?$", re.IGNORECASE)
MODEL_PATTERN = re.compile(r"\b[0-9]{1,2}[А-ЯA-Z]{1,3}[0-9]{2,3}[А-ЯA-Z]{0,2}\b")
ARTICLE_PATTERN = re.compile(r"\b[0-9А-ЯA-Z]{2,}\.[0-9]{2,}\.[0-9]{2,}\b")

# === Маркетинговые клише (НЕ пересекаются с FORBIDDEN_MARKETING из валидатора) ===
# Здесь — общие "вода" и хвастовство. В валидаторе остаётся прямой коммерческий запрет (купить/цена).
MARKETING_CLICHES = [
    "лучшая цена", "лучшее качество", "лучшее решение",
    "выгодное предложение", "уникальное предложение",
    "идеальный выбор", "идеальное решение",
    "высокое качество", "высочайшее качество",
    "огромный ассортимент", "широкий ассортимент",
    "оптимальная цена", "доступная цена",
    "передовые технологии", "инновационное решение",
]

# === Запрещённая лексика (перенесено из validate_pipeline.py) ===
FORBIDDEN_MARKETING = [
    r"купит[ьеи]", r"заказат[ьеи]", r"закаж[иу]те", r"закажем",
    r"цен[аыеуой]", r"стоимост[ьи]", r"скидк[аиу]", r"акци[яиюей]",
    r"доставк[аиу]", r"в наличии", r"со склада", r"под заказ",
    r"выгодно", r"выгодн[аоые][яеыйм]?",
]
FORBIDDEN_FIRST_PERSON = [
    r"\bмы\b", r"\bнаш[аеиуйюя]?\b", r"наша компания", r"наша организация",
    r"предлагаем", r"специализируемся", r"работаем",
]
FORBIDDEN_CTA = [
    r"обращайтесь", r"уточняйте", r"проконсультируйтесь",
    r"оставьте заявку", r"звоните", r"свяжитесь", r"напишите нам",
]
FORBIDDEN_INTROS = [
    r"^вот описание", r"^конечно", r"^хорошо,", r"^итак,",
]


# ============================================================================
# Очистка
# ============================================================================

def normalize_spaces(text: str) -> str:
    """Свернуть множественные пробелы и обрезать края."""
    return MULTISPACE_PATTERN.sub(" ", (text or "")).strip()


def clean_html_entities(text: str) -> str:
    """Удалить HTML-сущности типа &nbsp; &mdash; &#160;"""
    return HTML_ENTITY_PATTERN.sub(" ", text or "")


def clean_html_tags(text: str) -> str:
    """Удалить HTML-теги (<p>, <br>, <div> и т.п.)."""
    return HTML_TAG_PATTERN.sub(" ", text or "")


def clean_text(text: str) -> str:
    """
    Полная очистка для адаптеров: теги → сущности → пробелы.
    Идемпотентна: повторный вызов даёт тот же результат.
    """
    if not text:
        return ""
    t = clean_html_tags(text)
    t = clean_html_entities(t)
    t = normalize_spaces(t)
    return t


def count_html_artifacts(text: str) -> int:
    """Подсчитать число найденных HTML-сущностей и тегов (для логирования в адаптере)."""
    if not text:
        return 0
    return len(HTML_ENTITY_PATTERN.findall(text)) + len(HTML_TAG_PATTERN.findall(text))


# ============================================================================
# Извлечение
# ============================================================================

def extract_models(text: str) -> List[str]:
    """Извлечь модели станков (1М63Н, 16К40, РТ755Ф3)."""
    return MODEL_PATTERN.findall(text or "")


def extract_articles(text: str) -> List[str]:
    """Извлечь артикулы (16К40.03.152, 1М63Н.02.01.001)."""
    return ARTICLE_PATTERN.findall(text or "")


# ============================================================================
# Валидация
# ============================================================================

def validate_photo_url(url: Optional[str]) -> bool:
    """Базовая проверка URL фото."""
    if not url:
        return False
    return bool(PHOTO_URL_PATTERN.match(url))


def has_html_garbage(text: str) -> bool:
    """Остался ли HTML-мусор (теги или сущности)."""
    if not text:
        return False
    return bool(HTML_ENTITY_PATTERN.search(text)) or bool(HTML_TAG_PATTERN.search(text))


def has_marketing_cliche(text: str) -> bool:
    """Содержит ли текст маркетинговые клише ('лучшая цена', 'высокое качество' и т.п.)."""
    if not text:
        return False
    t = text.lower()
    return any(phrase in t for phrase in MARKETING_CLICHES)
