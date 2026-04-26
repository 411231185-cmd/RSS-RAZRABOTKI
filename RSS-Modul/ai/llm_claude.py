from typing import List

from .llm_base import LLMPrompt, LLMResult


class ClaudeClient:
    name = "claude"

    def __init__(self, model_name: str, api_key_env: str = "ANTHROPIC_API_KEY"):
        self.model_name = model_name
        self.api_key_env = api_key_env
        # здесь Клод потом добавит реальный клиент Anthropic

    def generate_batch(self, prompts: List[LLMPrompt]) -> List[LLMResult]:
        """
        Пока мок-реализация, чтобы пайплайны можно было запускать
        без реального API. Claude Code потом заменит на вызовы Anthropic.
        """
        results: List[LLMResult] = []
        for p in prompts:
            results.append(
                LLMResult(
                    id=p.id,
                    text=f"[MOCK CLAUDE OUTPUT for {p.id}]",
                    usage=None,
                    error=None,
                )
            )
        return results
