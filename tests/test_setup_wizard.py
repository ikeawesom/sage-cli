# tests/test_setup_wizard.py
"""Tests for sage.setup_wizard.run_setup_wizard.

Hermetic: no network, no reads/writes of the real ~/.sage/.env — the
global config path is monkeypatched to a tmp_path location for every test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sage import setup_wizard
from sage.setup_wizard import _read_example_defaults, run_setup_wizard


class FakeConsole:
    """Minimal console double: scripted `.input()` replies, records `.print()`."""

    def __init__(self, inputs: list[object]) -> None:
        self._inputs = list(inputs)
        self.printed: list[str] = []

    def print(self, *args: object, **kwargs: object) -> None:
        self.printed.append(" ".join(str(a) for a in args))

    def input(self, prompt: str = "", password: bool = False) -> str:
        value = self._inputs.pop(0)
        if isinstance(value, BaseException):
            raise value
        return str(value)


@pytest.fixture(autouse=True)
def global_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point GLOBAL_ENV_PATH at an isolated tmp_path location."""
    fake_path = tmp_path / "home" / ".sage" / ".env"
    monkeypatch.setattr(setup_wizard, "GLOBAL_ENV_PATH", fake_path)
    return fake_path


def test_completed_wizard_writes_env_with_entered_values_and_defaults(
    global_env_path: Path,
) -> None:
    console = FakeConsole(["https://example.invalid/v1", "sk-test-1234"])

    completed = run_setup_wizard(console)

    assert completed is True
    assert global_env_path.is_file()
    content = global_env_path.read_text(encoding="utf-8")
    assert "API_KEY=sk-test-1234" in content
    assert "BASE_URL=https://example.invalid/v1" in content

    defaults = _read_example_defaults()
    assert f"MODEL={defaults['MODEL']}" in content
    assert f"IMAGE_MODEL={defaults['IMAGE_MODEL']}" in content
    assert f"VERIFY_TLS={defaults['VERIFY_TLS']}" in content


def test_directory_created_even_when_missing(global_env_path: Path) -> None:
    assert not global_env_path.parent.exists()
    console = FakeConsole(["https://example.invalid/v1", "sk-test-1234"])

    run_setup_wizard(console)

    assert global_env_path.parent.is_dir()


def test_empty_input_reprompts_then_accepts(global_env_path: Path) -> None:
    console = FakeConsole(
        ["", "  ", "https://example.invalid/v1", "", "sk-test-1234"]
    )

    completed = run_setup_wizard(console)

    assert completed is True
    content = global_env_path.read_text(encoding="utf-8")
    assert "BASE_URL=https://example.invalid/v1" in content
    assert "API_KEY=sk-test-1234" in content


def test_keyboard_interrupt_at_base_url_aborts_without_writing(
    global_env_path: Path,
) -> None:
    console = FakeConsole([KeyboardInterrupt()])

    completed = run_setup_wizard(console)

    assert completed is False
    assert not global_env_path.is_file()


def test_keyboard_interrupt_at_api_key_aborts_without_writing(
    global_env_path: Path,
) -> None:
    console = FakeConsole(["https://example.invalid/v1", KeyboardInterrupt()])

    completed = run_setup_wizard(console)

    assert completed is False
    assert not global_env_path.is_file()


def test_eof_at_base_url_aborts_without_writing(global_env_path: Path) -> None:
    console = FakeConsole([EOFError()])

    completed = run_setup_wizard(console)

    assert completed is False
    assert not global_env_path.is_file()


def test_eof_at_api_key_aborts_without_writing(global_env_path: Path) -> None:
    console = FakeConsole(["https://example.invalid/v1", EOFError()])

    completed = run_setup_wizard(console)

    assert completed is False
    assert not global_env_path.is_file()


def test_read_example_defaults_missing_file_returns_fallbacks(
    tmp_path: Path,
) -> None:
    defaults = _read_example_defaults(tmp_path / "does-not-exist.env")
    assert defaults == {
        "MODEL": "claude-opus-4-8",
        "IMAGE_MODEL": "gemini-3-pro-image",
        "VERIFY_TLS": "false",
    }


def test_read_example_defaults_reads_repo_env_example() -> None:
    defaults = _read_example_defaults()
    assert defaults["MODEL"]
    assert defaults["IMAGE_MODEL"]
    assert defaults["VERIFY_TLS"]
