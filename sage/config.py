# sage/config.py
"""Configuration loading for the coding agent.

Loads API credentials, model settings, and TLS options from environment
variables. Configuration is resolved from (in order of precedence):

  1. Existing environment variables (highest priority).
  2. A local ./.env in the current working directory (per-project override).
  3. A global ~/.sage/.env (used when running `agent` anywhere).

This lets a single global config work from any folder, while still
allowing a project to drop its own .env to override specific values
(e.g. a different MODEL per project).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Global config location (works regardless of current directory).
GLOBAL_ENV_PATH = Path.home() / ".sage" / ".env"


def _load_env_files() -> None:
    """Load environment from local then global .env files.

    python-dotenv does NOT override variables that are already set, so:
      - real environment variables win over any .env file,
      - a local ./.env wins over the global ~/.sage/.env
        (because we load the local one first).
    """
    # 1. Local project override (current working directory), if present.
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
    # 2. Global fallback config.
    if GLOBAL_ENV_PATH.is_file():
        load_dotenv(dotenv_path=GLOBAL_ENV_PATH, override=False)


# Load configuration sources at import time.
_load_env_files()

DEFAULT_MODEL = "claude-opus-4-8"


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Runtime configuration for the agent.

    Attributes:
        api_key: Secret API key (never log this in full).
        base_url: OpenAI-compatible endpoint base URL.
        model: Model name to use for completions.
        ca_bundle: Optional path to a custom CA cert bundle (PEM).
        verify_tls: Whether to verify TLS certs. INSECURE if False.
    """

    api_key: str
    base_url: str
    model: str
    ca_bundle: str | None
    verify_tls: bool
    image_model: str

    def masked_key(self) -> str:
        """Return the API key with all but the last 4 chars masked."""
        if not self.api_key:
            return "(empty)"
        if len(self.api_key) <= 4:
            return "*" * len(self.api_key)
        return "*" * (len(self.api_key) - 4) + self.api_key[-4:]


def _parse_bool(value: str, default: bool) -> bool:
    """Parse a truthy/falsy env string into a bool.

    Args:
        value: The raw string value.
        default: Value to use when the string is empty.

    Returns:
        The parsed boolean.
    """
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    """Load configuration from environment variables.

    Returns:
        A populated, validated Config instance.

    Raises:
        ConfigError: If API_KEY or BASE_URL is missing/unset.
    """
    api_key = os.getenv("API_KEY", "").strip()
    base_url = os.getenv("BASE_URL", "").strip()
    model = os.getenv("MODEL", DEFAULT_MODEL).strip()
    image_model = os.getenv("IMAGE_MODEL", "gemini-3-pro-image").strip()

    ca_bundle = os.getenv("CA_BUNDLE", "").strip() or None
    verify_tls = _parse_bool(os.getenv("VERIFY_TLS", ""), default=True)

    if not api_key or api_key == "your-api-key-here":
        raise ConfigError(
            "Missing API_KEY. Set it in one of:\n"
            f"  - {GLOBAL_ENV_PATH} (global config)\n"
            "  - ./.env (per-project)\n"
            "  - or as an environment variable.\n"
            "Run setup.bat, or edit the config and set API_KEY."
        )

    if not base_url or base_url == "your-endpoint-url-here":
        raise ConfigError(
            "Missing BASE_URL (the endpoint URL). Set it in one of:\n"
            f"  - {GLOBAL_ENV_PATH} (global config)\n"
            "  - ./.env (per-project)\n"
            "  - or as an environment variable.\n"
            "Run setup.bat, or edit the config and set BASE_URL."
        )

    return Config(
        api_key=api_key,
        base_url=base_url,
        model=model,
        ca_bundle=ca_bundle,
        verify_tls=verify_tls,
        image_model=image_model,
    )