"""Provider-agnostic LLM client. Gemini is the only built-in backend."""

from __future__ import annotations

import json
import logging
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from src.budget import Budget
from src.cache import Cache, NullCache
from src.config import Settings
from src.errors import BudgetExceededError, OutputValidationError, TransientLLMError
from src.llm.jsonio import parse_json_object
from src.llm.prompts import build_repair_prompt, schema_instruction

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_TRANSIENT_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "unavailable",
    "resource_exhausted",
    "rate limit",
    "timeout",
    "timed out",
)


def is_transient_message(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _TRANSIENT_MARKERS)


class LLMBackend(Protocol):
    def generate(self, prompt: str, *, json_mode: bool = False) -> str: ...


class GeminiBackend:
    """Calls the official google-genai SDK. Constructing this does not call the API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed") from exc

        client = genai.Client(api_key=self.settings.gemini_api_key)
        config_kwargs: dict = {"temperature": self.settings.temperature}
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        try:
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            if is_transient_message(str(exc)):
                raise TransientLLMError(str(exc)) from exc
            raise
        text = getattr(response, "text", None) or ""
        if not text.strip():
            raise TransientLLMError("empty model response")
        return text


class LLMClient:
    def __init__(
        self,
        settings: Settings,
        backend: LLMBackend,
        cache: Cache | None = None,
        budget: Budget | None = None,
        sleeper=None,
    ) -> None:
        self.settings = settings
        self.backend = backend
        self.cache = cache if cache is not None else NullCache()
        self.budget = budget if budget is not None else Budget(settings)
        self._sleep = sleeper if sleeper is not None else _sleep

    def complete_text(self, prompt: str) -> str:
        material = self._material(prompt, json_mode=False, schema_name="")
        cached = self.cache.get("llm", material)
        if cached is not None:
            return cached
        text = self._generate_with_backoff(prompt, json_mode=False)
        self.cache.set("llm", material, text)
        return text

    def complete_model(self, prompt: str, schema: type[T]) -> T:
        full_prompt = f"{prompt}\n\n{schema_instruction(schema.model_json_schema())}"
        material = self._material(full_prompt, json_mode=True, schema_name=schema.__name__)
        cached = self.cache.get("llm", material)
        if cached is not None:
            return schema.model_validate(parse_json_object(cached))

        raw = self._generate_with_backoff(full_prompt, json_mode=True)
        last_error = "model output failed validation"
        attempts = self.settings.validation_repairs + 1
        for repair_index in range(attempts):
            try:
                obj = schema.model_validate(parse_json_object(raw))
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if repair_index >= self.settings.validation_repairs:
                    raise OutputValidationError(last_error) from exc
                logger.info("validation failed, requesting a repair: %s", last_error)
                raw = self._generate_with_backoff(
                    build_repair_prompt(full_prompt, raw, last_error),
                    json_mode=True,
                )
                continue
            self.cache.set("llm", material, json.dumps(obj.model_dump()))
            return obj
        raise OutputValidationError(last_error)

    def _generate_with_backoff(self, prompt: str, *, json_mode: bool) -> str:
        delay = self.settings.retry_base_seconds
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries):
            # Charge before the call so a cached retry storm cannot bypass the cap.
            self.budget.charge("llm")
            try:
                return self.backend.generate(prompt, json_mode=json_mode)
            except TransientLLMError as exc:
                last_error = exc
                if attempt >= self.settings.max_retries - 1:
                    break
                logger.info("transient LLM error, backing off %.2fs", delay)
                self._sleep(delay)
                delay *= 2
            except BudgetExceededError:
                raise
        assert last_error is not None
        raise last_error

    @staticmethod
    def _material(prompt: str, *, json_mode: bool, schema_name: str) -> str:
        return json.dumps(
            {"json_mode": json_mode, "schema": schema_name, "prompt": prompt},
            ensure_ascii=False,
        )


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
