from dataclasses import dataclass
from typing import Protocol, List, Dict, Any, Optional


@dataclass
class LLMPrompt:
    id: str
    text: str
    meta: Optional[Dict[str, Any]] = None


@dataclass
class LLMResult:
    id: str
    text: str
    usage: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class LLMClient(Protocol):
    name: str

    def generate_batch(self, prompts: List[LLMPrompt]) -> List[LLMResult]:
        ...
