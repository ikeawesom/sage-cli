# tests/test_cli.py
"""Tests for the CLI entry point and argument parsing."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import pytest

from sage.cli import CLIOptions, main, parse_args
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
