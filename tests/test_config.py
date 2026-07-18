# tests/test_config.py
"""Tests for sage.config.load_config and Config helpers.

All tests clear the config-related environment variables first so results
do not depend on the developer's real ~/.sage/.env or shell environment.
"""

from __future__ import annotations

import pytest

from sage.config import DEFAULT_MODEL, Config, ConfigError, load_config

ENV_VARS = ("API_KEY", "BASE_URL", "MODEL", "IMAGE_MODEL", "CA_BUNDLE", "VERIFY_TLS")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip all config env vars so each test starts from a blank slate."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_load_config_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "sk-test-1234")
    monkeypatch.setenv("BASE_URL", "https://example.invalid/v1")

    cfg = load_config()

    assert cfg.api_key == "sk-test-1234"
    assert cfg.base_url == "https://example.invalid/v1"
    assert cfg.model == DEFAULT_MODEL
    assert cfg.ca_bundle is None
    assert cfg.verify_tls is True


def test_load_config_missing_api_key() -> None:
    with pytest.raises(ConfigError, match="API_KEY"):
        load_config()


def test_load_config_missing_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "sk-test-1234")
    with pytest.raises(ConfigError, match="BASE_URL"):
        load_config()


def test_load_config_rejects_placeholder_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "your-api-key-here")
    monkeypatch.setenv("BASE_URL", "https://example.invalid/v1")
    with pytest.raises(ConfigError, match="API_KEY"):
        load_config()


def test_load_config_verify_tls_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "sk-test-1234")
    monkeypatch.setenv("BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("VERIFY_TLS", "false")

    assert load_config().verify_tls is False


def test_load_config_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "sk-test-1234")
    monkeypatch.setenv("BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("MODEL", "some-other-model")

    assert load_config().model == "some-other-model"


def test_masked_key_masks_all_but_last_four() -> None:
    cfg = Config(
        api_key="sk-test-1234",
        base_url="https://example.invalid/v1",
        model=DEFAULT_MODEL,
        ca_bundle=None,
        verify_tls=True,
        image_model="img-model",
    )
    masked = cfg.masked_key()
    assert masked.endswith("1234")
    assert "sk-test" not in masked
