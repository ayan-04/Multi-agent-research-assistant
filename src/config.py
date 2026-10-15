"""Runtime settings. Secrets come from the environment, never from source."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


class Settings(BaseModel):
    """Defaults target the Gemini free tier: a cheap Flash model and hard caps."""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    max_llm_calls: int = 12
    max_searches: int = 6
    max_fetches: int = 6
    max_embed_calls: int = 40
    max_steps: int = 40
    max_retries: int = 3
    retry_base_seconds: float = 0.5
    validation_repairs: int = 1
    critic_max_iterations: int = 2
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 4
    fetch_max_chars: int = 6000
    fetch_timeout_seconds: float = 15.0
    search_results_per_query: int = 2
    max_subquestions: int = 3
    cache_dir: str = "data/cache"
    chroma_dir: str = "data/chroma"
    temperature: float = 0.2

    def trimmed(self) -> Settings:
        """Return settings with caps that cannot go below 1 where a run needs them."""
        return self.model_copy(
            update={
                "max_llm_calls": max(0, self.max_llm_calls),
                "max_searches": max(0, self.max_searches),
                "max_fetches": max(0, self.max_fetches),
                "max_embed_calls": max(0, self.max_embed_calls),
                "max_steps": max(1, self.max_steps),
                "max_retries": max(1, self.max_retries),
                "validation_repairs": max(0, self.validation_repairs),
                "critic_max_iterations": max(1, min(self.critic_max_iterations, 2)),
                "chunk_size": max(1, self.chunk_size),
                "chunk_overlap": max(0, self.chunk_overlap),
                "top_k": max(1, self.top_k),
                "max_subquestions": max(1, min(self.max_subquestions, 4)),
                "search_results_per_query": max(1, self.search_results_per_query),
            }
        )


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def load_settings(env_file: str | Path | None = ".env") -> Settings:
    """Load `.env` if it exists, then read process environment variables."""
    if env_file is not None and Path(env_file).exists():
        load_dotenv(env_file, override=False)
    defaults = Settings()
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", defaults.gemini_api_key),
        gemini_model=os.getenv("GEMINI_MODEL", defaults.gemini_model),
        gemini_embed_model=os.getenv("GEMINI_EMBED_MODEL", defaults.gemini_embed_model),
        max_llm_calls=_int_env("MAX_LLM_CALLS", defaults.max_llm_calls),
        max_searches=_int_env("MAX_SEARCHES", defaults.max_searches),
        max_fetches=_int_env("MAX_FETCHES", defaults.max_fetches),
        max_embed_calls=_int_env("MAX_EMBED_CALLS", defaults.max_embed_calls),
        max_steps=_int_env("MAX_STEPS", defaults.max_steps),
        max_retries=_int_env("MAX_RETRIES", defaults.max_retries),
        retry_base_seconds=_float_env("RETRY_BASE_SECONDS", defaults.retry_base_seconds),
        validation_repairs=_int_env("VALIDATION_REPAIRS", defaults.validation_repairs),
        critic_max_iterations=_int_env("CRITIC_MAX_ITERATIONS", defaults.critic_max_iterations),
        chunk_size=_int_env("CHUNK_SIZE", defaults.chunk_size),
        chunk_overlap=_int_env("CHUNK_OVERLAP", defaults.chunk_overlap),
        top_k=_int_env("TOP_K", defaults.top_k),
        fetch_max_chars=_int_env("FETCH_MAX_CHARS", defaults.fetch_max_chars),
        fetch_timeout_seconds=_float_env("FETCH_TIMEOUT_SECONDS", defaults.fetch_timeout_seconds),
        search_results_per_query=_int_env(
            "SEARCH_RESULTS_PER_QUERY", defaults.search_results_per_query
        ),
        max_subquestions=_int_env("MAX_SUBQUESTIONS", defaults.max_subquestions),
        cache_dir=os.getenv("CACHE_DIR", defaults.cache_dir),
        chroma_dir=os.getenv("CHROMA_DIR", defaults.chroma_dir),
        temperature=_float_env("GEMINI_TEMPERATURE", defaults.temperature),
    ).trimmed()
