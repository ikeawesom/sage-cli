# tests/test_cli.py
"""Tests for the CLI entry point and argument parsing."""

from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path

import pytest

from sage import cli
from sage.cli import CLIOptions, main, parse_args
from sage.config import ConfigError
from sage.modes import Mode

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_main_is_callable() -> None:
    assert callable(main)


def test_pyproject_entry_point_resolves() -> None:
    """The `sage` console script in pyproject.toml must resolve to a callable."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    entry = data["project"]["scripts"]["sage"]
    module_name, _, attr = entry.partition(":")
    module = importlib.import_module(module_name)
    assert callable(getattr(module, attr))


def test_parse_args_defaults() -> None:
    opts = parse_args([])
    assert isinstance(opts, CLIOptions)
    assert opts.mode == Mode.from_str("normal")
    assert opts.model is None
    assert opts.root == "."
    assert opts.verbose is True
    assert opts.plain is False


def test_parse_args_auto_alias() -> None:
    assert parse_args(["--auto"]).mode == Mode.from_str("auto")
    assert parse_args(["-y"]).mode == Mode.from_str("auto")


def test_parse_args_model_and_root() -> None:
    opts = parse_args(["--model", "my-model", "--root", "some/dir", "--plain"])
    assert opts.model == "my-model"
    assert opts.root == "some/dir"
    assert opts.plain is True


def test_parse_args_invalid_mode_exits() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--mode", "not-a-mode"])


def test_version_flag_exits_and_prints(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        parse_args(["--version"])
    assert excinfo.value.code == 0
    assert "Sage" in capsys.readouterr().out


# ── First-run setup wizard trigger (main()) ─────────────────────────


class _AlwaysFailsREPL:
    """Stand-in REPL whose constructor always raises ConfigError."""

    def __init__(self, options: CLIOptions) -> None:
        raise ConfigError("boom: missing config")


def test_missing_global_file_non_tty_skips_wizard_no_hang(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-interactive stdin must never trigger the wizard (scripts/CI)."""
    monkeypatch.setattr(cli, "GLOBAL_ENV_PATH", tmp_path / ".sage" / ".env")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(cli, "REPL", _AlwaysFailsREPL)

    def _wizard_should_not_run() -> bool:
        raise AssertionError("wizard must not run when stdin is non-interactive")

    monkeypatch.setattr(cli, "run_setup_wizard", _wizard_should_not_run)

    exit_code = main([])

    assert exit_code == 1
    assert "[config error]" in capsys.readouterr().err


def test_existing_global_file_skips_wizard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A bad/incomplete existing global file keeps the plain error path."""
    env_path = tmp_path / ".sage" / ".env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text("API_KEY=\nBASE_URL=\n", encoding="utf-8")
    monkeypatch.setattr(cli, "GLOBAL_ENV_PATH", env_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "REPL", _AlwaysFailsREPL)

    def _wizard_should_not_run() -> bool:
        raise AssertionError("wizard must not run when the global file already exists")

    monkeypatch.setattr(cli, "run_setup_wizard", _wizard_should_not_run)

    exit_code = main([])

    assert exit_code == 1
    assert "[config error]" in capsys.readouterr().err


def test_aborted_wizard_exits_1_and_reoffers_next_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An aborted wizard writes no file, so the trigger condition still
    holds on the next invocation and the wizard is offered again."""
    env_path = tmp_path / ".sage" / ".env"
    monkeypatch.setattr(cli, "GLOBAL_ENV_PATH", env_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "REPL", _AlwaysFailsREPL)

    calls = {"count": 0}

    def _wizard_aborts() -> bool:
        calls["count"] += 1
        return False

    monkeypatch.setattr(cli, "run_setup_wizard", _wizard_aborts)

    exit_code = main([])
    assert exit_code == 1
    assert calls["count"] == 1
    assert not env_path.exists()
    assert "Setup cancelled" in capsys.readouterr().err

    # Second invocation: trigger condition (missing file + tty) still holds.
    exit_code_again = main([])
    assert exit_code_again == 1
    assert calls["count"] == 2
    assert not env_path.exists()


def test_completed_wizard_retries_config_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed wizard retries config loading and hands off to run()."""
    monkeypatch.setattr(cli, "GLOBAL_ENV_PATH", tmp_path / ".sage" / ".env")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "run_setup_wizard", lambda: True)

    class _RetryREPL:
        """First construction fails (pre-wizard); second succeeds (post-wizard)."""

        attempts = 0

        def __init__(self, options: CLIOptions) -> None:
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise ConfigError("boom: missing config")

        def run(self) -> int:
            return 0

    monkeypatch.setattr(cli, "REPL", _RetryREPL)

    exit_code = main([])

    assert exit_code == 0
    assert _RetryREPL.attempts == 2
