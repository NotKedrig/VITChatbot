"""
app/llm/provider.py — LLM provider abstraction (Phase 2).

Provides a unified .complete(prompt, temperature=0) interface backed by
a concrete LLM provider selected via app/config.settings.llm_provider.

Supported providers
-------------------
"google"   — Google Gemini via google-generativeai SDK.
              API key env var: GEMINI_API_KEY (or set llm_api_key_env to override).
"openai"   — OpenAI via openai SDK.
              API key env var: OPENAI_API_KEY.
"ollama"   — Local Ollama (OpenAI-compatible REST API, no key needed).
              Set LLM_BASE_URL=http://localhost:11434 in .env.

Every provider records model_name and model_version in the returned
LLMResponse so the experiment runner can write them to results CSVs.

Caching
-------
Every .complete() call is cached by app/llm/cache.py (keyed on
prompt_hash + model + temperature).  Pass use_cache=False to bypass.

No AWS services are used.
"""

from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, Type

from pydantic import BaseModel

from app.llm.cache import LLMCache, make_cache_key
from app.logging_config import log_llm_call

logger = logging.getLogger(__name__)

class QuotaExhaustedError(Exception):
    """Raised when the daily LLM API quota is completely exhausted."""
    pass

# ---------------------------------------------------------------------------
# Public response type
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    """
    Unified response object returned by every provider's .complete() call.

    Fields recorded verbatim in results CSVs to ensure reproducibility
    (Section 10.2 of the master plan).
    """
    text: str                   # The generated answer text
    model_name: str             # Fully-qualified model name (e.g. "gemini-2.0-flash")
    model_version: str          # Version string (mirrors model_name where provider
                                #  doesn't expose a separate version field)
    temperature: float          # Temperature used for generation
    prompt_hash: str            # SHA-256 hex of the prompt (for audit trail)
    cached: bool = False        # True if the response came from LLMCache
    raw: dict[str, Any] = field(default_factory=dict)  # Provider-specific raw response

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "temperature": self.temperature,
            "prompt_hash": self.prompt_hash,
            "cached": self.cached,
        }


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

class LLMProvider(Protocol):
    """Interface every concrete provider must satisfy."""

    def complete(
        self,
        prompt: str,
        temperature: float = 0.0,
        use_cache: bool = True,
        response_schema: Type[BaseModel] | None = None,
    ) -> LLMResponse:
        ...

    @property
    def model_name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Google Gemini provider
# ---------------------------------------------------------------------------

class GeminiProvider:
    """
    Google Gemini provider using the google-generativeai SDK.

    API key is read from the environment variable named in
    settings.llm_api_key_env (default: GEMINI_API_KEY).
    """

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash",
        api_key_env: str = "GEMINI_API_KEY",
        cache: LLMCache | None = None,
    ) -> None:
        self._model_name = model_name
        self._api_key_env = api_key_env
        self._cache = cache or LLMCache()
        self._client = None  # lazy init

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai"
            ) from exc

        api_key = os.environ.get(self._api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Gemini API key not found. Set the environment variable "
                f"'{self._api_key_env}' in your .env file.\n"
                f"Get a free key at: https://aistudio.google.com/apikey"
            )
        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(self._model_name)
        return self._client

    def complete(
        self,
        prompt: str,
        temperature: float = 0.0,
        use_cache: bool = True,
        response_schema: Type[BaseModel] | None = None,
    ) -> LLMResponse:
        # Include schema name in cache key if provided
        schema_suffix = f"_schema_{response_schema.__name__}" if response_schema else ""
        cache_key, prompt_hash = make_cache_key(prompt + schema_suffix, self._model_name, temperature)

        # --- Cache lookup ---
        if use_cache:
            cached_resp = self._cache.get(
                prompt, self._model_name, temperature, use_cache=True
            )
            if cached_resp is not None:
                return LLMResponse(
                    text=cached_resp["text"],
                    model_name=self._model_name,
                    model_version=cached_resp.get("model_version", self._model_name),
                    temperature=temperature,
                    prompt_hash=prompt_hash,
                    cached=True,
                    raw=cached_resp,
                )

        # --- Live call (with 5 RPM rate limiting & exponential backoff) ---
        client = self._get_client()
        import google.generativeai as genai  # type: ignore
        from google.api_core.exceptions import ResourceExhausted

        generation_kwargs = {
            "temperature": temperature,
            "candidate_count": 1,
        }
        if response_schema is not None:
            generation_kwargs["response_mime_type"] = "application/json"
            generation_kwargs["response_schema"] = response_schema

        generation_config = genai.GenerationConfig(**generation_kwargs)

        max_retries = 3
        base_delay = 12.0  # 12 seconds = 5 RPM
        
        for attempt in range(max_retries + 1):
            try:
                # Always sleep base_delay to respect 5 RPM limit
                time.sleep(base_delay)
                
                response = client.generate_content(
                    prompt,
                    generation_config=generation_config,
                )
                text = response.text
                break
            except ResourceExhausted as exc:
                error_msg = str(exc).lower()
                # If we hit the daily free tier limit, stop immediately.
                if "free_tier_requests" in error_msg and "limit: 20" in error_msg:
                    logger.error("Daily Quota Exhausted!")
                    raise QuotaExhaustedError("Gemini Free Tier daily quota of 20 requests reached.") from exc
                
                if attempt == max_retries:
                    logger.error("Max retries reached for 429 rate limit.")
                    raise
                
                sleep_time = base_delay * (2 ** attempt)
                logger.warning(f"429 Rate limit hit, backing off for {sleep_time} seconds (attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
            except Exception as exc:
                logger.error("Gemini API call failed", extra={"error": str(exc)})
                raise

        response_dict = {
            "text": text,
            "model_name": self._model_name,
            "model_version": self._model_name,  # Gemini doesn't expose sub-version
            "temperature": temperature,
            "prompt_hash": prompt_hash,
        }

        # --- Cache store ---
        self._cache.set(prompt, self._model_name, temperature, response_dict)

        log_llm_call(
            logger,
            prompt_hash=prompt_hash,
            model_name=self._model_name,
            temperature=temperature,
            cached=False,
        )

        return LLMResponse(
            text=text,
            model_name=self._model_name,
            model_version=self._model_name,
            temperature=temperature,
            prompt_hash=prompt_hash,
            cached=False,
            raw=response_dict,
        )


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIProvider:
    """
    OpenAI provider.  API key from OPENAI_API_KEY env var.
    Also works with Ollama (OpenAI-compatible): set base_url to Ollama endpoint.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o-2024-05-13",
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str = "",
        cache: LLMCache | None = None,
    ) -> None:
        self._model_name = model_name
        self._api_key_env = api_key_env
        self._base_url = base_url
        self._cache = cache or LLMCache()
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai"
            ) from exc

        api_key = os.environ.get(self._api_key_env, "ollama")  # Ollama ignores key
        kwargs: dict[str, Any] = {"api_key": api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def complete(
        self,
        prompt: str,
        temperature: float = 0.0,
        use_cache: bool = True,
        response_schema: Type[BaseModel] | None = None,
    ) -> LLMResponse:
        schema_suffix = f"_schema_{response_schema.__name__}" if response_schema else ""
        _, prompt_hash = make_cache_key(prompt + schema_suffix, self._model_name, temperature)

        if use_cache:
            cached_resp = self._cache.get(
                prompt, self._model_name, temperature, use_cache=True
            )
            if cached_resp is not None:
                return LLMResponse(
                    text=cached_resp["text"],
                    model_name=self._model_name,
                    model_version=cached_resp.get("model_version", self._model_name),
                    temperature=temperature,
                    prompt_hash=prompt_hash,
                    cached=True,
                    raw=cached_resp,
                )

        client = self._get_client()
        kwargs = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if response_schema is not None:
            # Note: Basic JSON object forcing for fallback providers.
            kwargs["response_format"] = {"type": "json_object"}
            
        completion = client.chat.completions.create(**kwargs)
        text = completion.choices[0].message.content or ""
        model_version = completion.model or self._model_name

        response_dict = {
            "text": text,
            "model_name": self._model_name,
            "model_version": model_version,
            "temperature": temperature,
            "prompt_hash": prompt_hash,
        }
        self._cache.set(prompt, self._model_name, temperature, response_dict)

        log_llm_call(logger, prompt_hash=prompt_hash, model_name=self._model_name,
                     temperature=temperature, cached=False)

        return LLMResponse(
            text=text, model_name=self._model_name, model_version=model_version,
            temperature=temperature, prompt_hash=prompt_hash, cached=False,
            raw=response_dict,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_provider_singleton: GeminiProvider | OpenAIProvider | None = None


def get_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    api_key_env: str | None = None,
    base_url: str | None = None,
    cache: LLMCache | None = None,
) -> GeminiProvider | OpenAIProvider:
    """
    Return the configured LLM provider.

    Reads defaults from app/config.settings if not supplied.
    Singleton: the same provider object is returned on subsequent calls
    with identical parameters.
    """
    global _provider_singleton

    from app.config import settings

    provider_name = provider_name or settings.llm_provider
    model_name = model_name or settings.llm_model_name
    api_key_env = api_key_env or settings.llm_api_key_env
    base_url = base_url or settings.llm_base_url

    # Invalidate singleton if key params changed
    if _provider_singleton is not None:
        if _provider_singleton.model_name == model_name:
            return _provider_singleton

    if provider_name in ("google", "gemini"):
        prov = GeminiProvider(
            model_name=model_name,
            api_key_env=api_key_env or "GEMINI_API_KEY",
            cache=cache,
        )
    elif provider_name in ("openai", "ollama"):
        prov = OpenAIProvider(
            model_name=model_name,
            api_key_env=api_key_env or "OPENAI_API_KEY",
            base_url=base_url or ("http://localhost:11434/v1" if provider_name == "ollama" else ""),
            cache=cache,
        )
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name!r}. "
            "Supported: 'google', 'openai', 'ollama'."
        )

    _provider_singleton = prov
    logger.info(
        "LLM provider initialised",
        extra={"provider": provider_name, "model": model_name},
    )
    return prov
