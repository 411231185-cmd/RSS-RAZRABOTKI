from core.logging_config import get_logger
from ai.llm_claude import ClaudeClient
from ai.prompt_loader import load_prompt
from ai.llm_base import LLMPrompt

logger = get_logger(__name__)


def generate_descriptions(model_id: str = "claude-sonnet", code_prefix: str | None = None) -> None:
    """
    Flow B: заглушка пайплайна генерации описаний.
    Сейчас просто дергает мок-CLAUDE для теста.
    """
    logger.info("generate_descriptions start: model_id=%s, code_prefix=%s", model_id, code_prefix)

    client = ClaudeClient(model_name="claude-3.5-sonnet")
    template = load_prompt("description_generic")

    prompts = [
        LLMPrompt(
            id="test-1",
            text=template.replace("{{ code }}", "TEST-CODE")
                         .replace("{{ name }}", "Тестовая деталь")
                         .replace("{{ category }}", "Тестовая категория")
                         .replace("{{ extra }}", "дополнительные данные"),
        ),
    ]

    results = client.generate_batch(prompts)
    for r in results:
        logger.info("Generated text for id=%s: %s", r.id, r.text[:120])

    logger.info("generate_descriptions finished (stub)")
