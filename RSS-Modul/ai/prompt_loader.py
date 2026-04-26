from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "configs" / "ai" / "prompts"


def load_prompt(prompt_code: str) -> str:
    """
    Пока: один шаблон description_generic.md.
    Потом можно сделать: код -> отдельный файл.
    """
    path = PROMPTS_DIR / "description_generic.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
