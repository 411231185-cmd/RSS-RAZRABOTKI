SERVICESBLOCK_HTML = """
<!-- SERVICESBLOCK START -->
<!-- фиксированный HTML-блок перелинковки td-rss.ru (текст правится только в одном месте) -->
<!-- SERVICESBLOCK END -->
""".strip()


def ensure_servicesblock(text: str) -> str:
    """
    Если SERVICESBLOCK уже есть в тексте — ничего не делаем.
    Если нет — добавляем в конец.
    """
    marker = "SERVICESBLOCK START"
    if marker in text:
        return text
    if not text.endswith("\n"):
        text = text + "\n"
    return text + "\n" + SERVICESBLOCK_HTML
