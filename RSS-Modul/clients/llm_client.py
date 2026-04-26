# clients/llm_client.py

from dataclasses import dataclass
from typing import Protocol, Tuple
import os

from core.description_policy import SERVICESBLOCK

# Попробуем импортировать SDK, но не падаем, если его нет — это на совести среды
try:
    import anthropic  # type: ignore
except ImportError:
    anthropic = None

try:
    import openai  # type: ignore
except ImportError:
    openai = None


class LLMClient(Protocol):
    def generate_description(self, prompt: str) -> str:
        ...


@dataclass
class LLMClientStub:
    """
    Заглушка для отладки пайплайна без реальных вызовов LLM.
    """

    def generate_description(self, prompt: str) -> str:
        text = (
            "Инженерное описание будет сгенерировано реальной моделью. "
            "Текущий текст — заглушка для отладки пайплайна."
        )
        return f"{text}\n\n{SERVICESBLOCK}"


@dataclass
class AnthropicClient:
    model: str
    max_tokens: int = 800

    def __post_init__(self):
        if anthropic is None:
            raise RuntimeError("Пакет 'anthropic' не установлен (pip install anthropic).")
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            raise RuntimeError("Не задан ANTHROPIC_API_KEY / CLAUDE_API_KEY в переменных среды.")
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate_description(self, prompt: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        # Берём первый текстовый блок
        return resp.content[0].text


@dataclass
class OpenAIClient:
    model: str
    max_tokens: int = 800

    def __post_init__(self):
        if openai is None:
            raise RuntimeError("Пакет 'openai' не установлен (pip install openai).")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Не задан OPENAI_API_KEY в переменных среды.")
        openai.api_key = api_key

    def generate_description(self, prompt: str) -> str:
        # Адаптируй под актуальный метод OpenAI (chat.completions или messages)
        resp = openai.ChatCompletion.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
        )
        return resp["choices"][0]["message"]["content"]


@dataclass
class LLMClientRouter:
    """
    Универсальный роутер по провайдеру/модели.

    Формат model_id:
      - "anthropic:claude-haiku-4.5"
      - "anthropic:claude-sonnet-4.6"
      - "openai:gpt-4.1-mini"
      - просто "claude-haiku-4.5" → по умолчанию anthropic
    """

    model_id: str

    def _split(self) -> Tuple[str, str]:
        if ":" in self.model_id:
            provider, name = self.model_id.split(":", 1)
            return provider.strip().lower(), name.strip()
        # по умолчанию считаем, что это Anthropic
        return "anthropic", self.model_id.strip()

    def generate_description(self, prompt: str) -> str:
        provider, name = self._split()

        if provider == "anthropic":
            client = AnthropicClient(model=name)
        elif provider == "openai":
            client = OpenAIClient(model=name)
        elif provider == "stub":
            client = LLMClientStub()
        else:
            # дефолт: безопасный дешевый вариант
            client = AnthropicClient(model="claude-haiku-4.5")

        return client.generate_description(prompt)