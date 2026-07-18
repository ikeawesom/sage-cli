# sage/setup_wizard.py
"""Interactive first-run setup wizard.

When a user runs `sage` with no global configuration yet, this module
walks them through creating `~/.sage/.env` interactively instead of
just failing with a config error.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from sage.config import GLOBAL_ENV_PATH

# Repo-relative path to the .env.example template this wizard reads its
# non-secret defaults (MODEL, IMAGE_MODEL, VERIFY_TLS) from.
ENV_EXAMPLE_PATH = Path(__file__).resolve().parent.parent / ".env.example"

# .env.example is not shipped in the wheel, so installed copies (pipx)
# fall back to these values; keep them in sync with .env.example.
_FALLBACK_DEFAULTS = {
    "MODEL": "claude-opus-4-8",
    "IMAGE_MODEL": "gemini-3-pro-image",
    "VERIFY_TLS": "false",
}


def _read_example_defaults(path: Path = ENV_EXAMPLE_PATH) -> dict[str, str]:
    """Read the MODEL/IMAGE_MODEL/VERIFY_TLS defaults from `.env.example`.

    Args:
        path: Path to the `.env.example` template.

    Returns:
        A dict mapping each key in `_FALLBACK_DEFAULTS` to the template's
        value, or to the baked-in fallback when the file or key is missing
        (the template is absent in installed copies).
    """
    defaults = dict(_FALLBACK_DEFAULTS)
    if not path.is_file():
        return defaults
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key in defaults:
            defaults[key] = value.strip()
    return defaults


def _prompt_required(console: Console, label: str, *, password: bool = False) -> str:
    """Prompt for a required value, re-prompting while it is empty.

    Args:
        console: The rich console (or console-like object) to prompt on.
        label: The field label shown to the user.
        password: Whether to mask input (used for API_KEY).

    Returns:
        The trimmed, non-empty value entered.

    Raises:
        KeyboardInterrupt: If the user cancels (Ctrl-C).
        EOFError: If input is closed (Ctrl-D / piped EOF).
    """
    while True:
        value = console.input(f"{label}: ", password=password).strip()
        if value:
            return value
        console.print(f"[red]{label} is required.[/]")


def run_setup_wizard(console: Console | None = None) -> bool:
    """Interactively create `~/.sage/.env` on first run.

    Args:
        console: Optional rich console (a fresh one is created if omitted;
            tests may inject a fake console-like object exposing
            `.input(prompt, password=False)` and `.print(*args)`).

    Returns:
        True if setup completed and the config file was written.
        False if the user aborted (Ctrl-C / EOF) — in which case no file
        is written, so `sage` will offer the wizard again next run.
    """
    console = console or Console()

    console.print(
        "[bold cyan]Welcome to Sage![/] It looks like this is your first run.\n"
        f"Let's set up your configuration ([dim]{GLOBAL_ENV_PATH}[/]).\n"
        "[dim]Press Ctrl-C at any time to cancel.[/]"
    )

    # Safe to create even if the user aborts — an empty directory is not
    # a partial config file.
    GLOBAL_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        base_url = _prompt_required(console, "BASE_URL (API endpoint URL)")
        api_key = _prompt_required(console, "API_KEY", password=True)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Setup cancelled. No configuration was saved.[/]")
        return False

    defaults = _read_example_defaults()

    # Compose the full file content up front so the write below is a
    # single atomic operation — partial input must never produce a file.
    content = "\n".join(
        [
            "# Created by Sage's first-run setup wizard.",
            f"API_KEY={api_key}",
            f"BASE_URL={base_url}",
            f"MODEL={defaults['MODEL']}",
            f"VERIFY_TLS={defaults['VERIFY_TLS']}",
            f"IMAGE_MODEL={defaults['IMAGE_MODEL']}",
            "",
        ]
    )
    GLOBAL_ENV_PATH.write_text(content, encoding="utf-8")

    console.print(f"[green]Configuration saved to[/] [cyan]{GLOBAL_ENV_PATH}[/]")
    return True
