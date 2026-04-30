"""
Обёртка над Anthropic API с поддержкой параллельной генерации.

Mock-режим: если ANTHROPIC_API_KEY не задан, возвращает предсказуемые заглушки.
Параллелизм: ThreadPoolExecutor для I/O-bound запросов к API.
Ретраи: экспоненциальный backoff на rate limit и временные сетевые ошибки.
"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

logger = logging.getLogger(__name__)

_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Дефолтные параметры ретраев. Можно переопределить через init.
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2.0  # 2с, 4с, 8с
DEFAULT_PROGRESS_EVERY = 25  # лог каждые N товаров


class ClaudeClient:
    """
    Клиент Anthropic API.

    Параметры:
        model_id:       идентификатор модели.
        max_workers:    параллельных потоков для generate_batch (1 = последовательно).
        max_retries:    попыток на один запрос при rate limit / сетевых ошибках.
        backoff_base:   база экспоненциального backoff в секундах.
    """

    def __init__(
        self,
        model_id: str = "claude-sonnet-4-20250514",
        max_workers: int = 1,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
    ):
        self.model_id = model_id
        self.max_workers = max(1, max_workers)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._mock = _API_KEY is None

        if self._mock:
            logger.warning(
                "ANTHROPIC_API_KEY не задан — ClaudeClient работает в MOCK-режиме"
            )
            self._client = None
        else:
            import anthropic
            self._client = anthropic.Anthropic(api_key=_API_KEY)

    # ------------------------------------------------------------------ public

    def generate(self, prompt: str, max_tokens: int = 400) -> str:
        """Сгенерировать один ответ. Делает ретраи внутри."""
        if self._mock:
            return self._mock_response(prompt)
        return self._call_with_retries(prompt, max_tokens)

    def generate_batch(
        self,
        prompts: List[str],
        max_tokens: int = 400,
        delay_seconds: float = 0.0,
        max_workers: Optional[int] = None,
        progress_every: int = DEFAULT_PROGRESS_EVERY,
    ) -> List[str]:
        """
        Сгенерировать описания для списка промтов.

        Args:
            prompts:        список промтов (порядок результатов сохраняется).
            max_tokens:     лимит токенов на ответ.
            delay_seconds:  пауза между запросами в последовательном режиме (rate-limit guard).
            max_workers:    переопределить self.max_workers только для этого вызова.
            progress_every: логировать прогресс каждые N товаров.

        Returns:
            список строк-ответов в исходном порядке prompts.
        """
        workers = max_workers if max_workers is not None else self.max_workers
        total = len(prompts)
        if total == 0:
            return []

        logger.info("generate_batch: %d промтов, workers=%d, mock=%s",
                    total, workers, self._mock)

        if workers == 1:
            return self._run_sequential(prompts, max_tokens, delay_seconds, progress_every)
        return self._run_parallel(prompts, max_tokens, workers, progress_every)

    # ------------------------------------------------------------- internals

    def _mock_response(self, prompt: str) -> str:
        return (
            f"[MOCK] Описание для промта длиной {len(prompt)} символов. "
            "Деталь предназначена для использования в промышленных станках. "
            "Обеспечивает надёжную работу узла. "
            "Совместима с моделями, указанными в технической документации. "
            "Параметры выполняются по конструкторской документации."
        )

    def _call_with_retries(self, prompt: str, max_tokens: int) -> str:
        """Один вызов API с ретраями на временные ошибки."""
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.messages.create(
                    model=self.model_id,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text.strip()
            except Exception as e:
                last_err = e
                if not self._is_retryable(e) or attempt == self.max_retries - 1:
                    raise
                wait = self.backoff_base ** (attempt + 1)
                logger.warning(
                    "API error (attempt %d/%d): %s — retry in %.1fs",
                    attempt + 1, self.max_retries, e, wait,
                )
                time.sleep(wait)
        # сюда не попадаем, но на всякий
        raise RuntimeError(f"Unreachable: last_err={last_err}")

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Решить, имеет ли смысл повтор."""
        name = exc.__class__.__name__
        # Anthropic SDK: RateLimitError, APIConnectionError, InternalServerError, APITimeoutError
        if name in {"RateLimitError", "APIConnectionError", "APITimeoutError",
                    "InternalServerError", "ServiceUnavailableError"}:
            return True
        # Если SDK не подгружен или ошибка другая — смотрим текст
        msg = str(exc).lower()
        return any(s in msg for s in ("rate limit", "429", "timeout", "connection",
                                       "503", "502", "overloaded"))

    def _run_sequential(
        self, prompts: List[str], max_tokens: int,
        delay_seconds: float, progress_every: int,
    ) -> List[str]:
        results: List[str] = []
        total = len(prompts)
        for i, prompt in enumerate(prompts):
            if self._mock:
                results.append(self._mock_response(prompt))
            else:
                results.append(self._call_with_retries(prompt, max_tokens))
                if i < total - 1 and delay_seconds > 0:
                    time.sleep(delay_seconds)
            if (i + 1) % progress_every == 0 or (i + 1) == total:
                logger.info("  progress: %d/%d", i + 1, total)
        return results

    def _run_parallel(
        self, prompts: List[str], max_tokens: int,
        workers: int, progress_every: int,
    ) -> List[str]:
        """
        Параллельная генерация через ThreadPoolExecutor.

        Используем executor.map для сохранения порядка результатов.
        Прогресс считаем по counter — он атомарный для int в CPython.
        """
        total = len(prompts)
        results: List[Optional[str]] = [None] * total
        completed = [0]  # обёртка для замыкания

        def worker(idx_prompt):
            idx, prompt = idx_prompt
            if self._mock:
                out = self._mock_response(prompt)
            else:
                out = self._call_with_retries(prompt, max_tokens)
            completed[0] += 1
            done = completed[0]
            if done % progress_every == 0 or done == total:
                logger.info("  progress: %d/%d", done, total)
            return idx, out

        start = time.time()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for idx, content in executor.map(worker, enumerate(prompts)):
                results[idx] = content
        elapsed = time.time() - start
        rate = total / elapsed if elapsed > 0 else 0
        logger.info("Параллельная генерация: %d товаров за %.1fс (%.1f items/s)",
                    total, elapsed, rate)

        return [r if r is not None else "" for r in results]