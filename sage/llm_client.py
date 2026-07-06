# sage/llm_client.py  (changes only — shown as full file for clarity)
"""Defensive wrapper around the OpenAI-compatible chat API.

Provides a single LLMClient class that:
  - Builds a TLS-aware client from config (shared factory).
  - Retries transient failures with exponential backoff.
  - Surfaces clean, actionable errors (no raw stack traces).
  - Supports native tool calling and optional streaming.
  - Optionally shows a spinner around network calls ONLY (never tools),
    to avoid deadlocking interactive confirmation prompts.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.chat import ChatCompletion, ChatCompletionMessage

from sage.config import Config, load_config
from sage.http import build_http_client

_RETRYABLE = (APIConnectionError, APITimeoutError, RateLimitError)


class LLMError(Exception):
    """User-facing error raised when an LLM call cannot be completed."""


class LLMClient:
    """A thin, defensive wrapper over the OpenAI chat completions API."""

    def __init__(
        self,
        config: Config | None = None,
        *,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        request_timeout: float = 120.0,
        console: Any | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            config: Optional pre-loaded config. If None, loads from env.
            max_retries: Max retry attempts for transient errors.
            base_backoff: Base seconds for exponential backoff.
            request_timeout: Per-request timeout in seconds.
            console: Optional rich Console for a network-only spinner.
        """
        self.config = config or load_config()
        self.model = self.config.model
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._console = console

        http_client = build_http_client(self.config)
        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            http_client=http_client,
            timeout=request_timeout,
            max_retries=0,
        )

    @contextmanager
    def _thinking(self) -> Iterator[None]:
        """Show a spinner during a network call, if a console is set."""
        if self._console is None:
            yield
            return
        with self._console.status("[dim]thinking…[/]", spinner="dots"):
            yield

    # ── Public API ────────────────────────────────────────────────

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
        max_tokens: int = 4096,
        temperature: float | None = None,
    ) -> ChatCompletionMessage:
        """Send a chat request and return the assistant's message."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = list(tools)
            kwargs["tool_choice"] = tool_choice
        if temperature is not None:
            kwargs["temperature"] = temperature

        completion: ChatCompletion = self._request(**kwargs)
        return completion.choices[0].message

    def chat(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        max_tokens: int = 4096,
        temperature: float | None = None,
    ) -> str:
        """Send a chat request and return the assistant's text content."""
        message = self.complete(
            messages, max_tokens=max_tokens, temperature=temperature
        )
        return message.content or ""

    def stream(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        max_tokens: int = 4096,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Stream the assistant's text content chunk by chunk."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "stream": True,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            stream = self._client.chat.completions.create(**kwargs)
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise LLMError(self._explain(exc)) from exc
        except _RETRYABLE as exc:
            raise LLMError(self._explain(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Unexpected streaming error: {exc}") from exc

    # ── Internals ─────────────────────────────────────────────────

    def _request(self, **kwargs: Any) -> ChatCompletion:
        """Perform a completion request with retry/backoff (spinner-wrapped)."""
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                with self._thinking():
                    return self._client.chat.completions.create(**kwargs)
            except (AuthenticationError, PermissionDeniedError) as exc:
                raise LLMError(self._explain(exc)) from exc
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    backoff = self._base_backoff * (2 ** (attempt - 1))
                    print(
                        f"[llm] transient error ({type(exc).__name__}); "
                        f"retry {attempt}/{self._max_retries - 1} in {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue
            except Exception as exc:  # noqa: BLE001
                raise LLMError(f"Unexpected API error: {exc}") from exc

        raise LLMError(
            f"API call failed after {self._max_retries} attempts: "
            f"{self._explain(last_exc) if last_exc else 'unknown error'}"
        )

    @staticmethod
    def _explain(exc: Exception | None) -> str:
        """Map an exception to a concise, actionable message."""
        if isinstance(exc, AuthenticationError):
            return "Authentication failed — check API_KEY in .env."
        if isinstance(exc, PermissionDeniedError):
            return (
                "Access denied (403) — your team may not be allowed to use "
                "this MODEL. Run whoami.py to list allowed models."
            )
        if isinstance(exc, RateLimitError):
            return "Rate limited (429) — slow down or retry later."
        if isinstance(exc, APITimeoutError):
            return "Request timed out — the model took too long to respond."
        if isinstance(exc, APIConnectionError):
            return (
                "Connection error — check network/VPN and TLS settings "
                "(CA_BUNDLE / VERIFY_TLS)."
            )
        return str(exc) if exc else "unknown error"