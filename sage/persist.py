# sage/persist.py
"""Persist user preferences back to the global .env config.

Currently supports updating the MODEL setting so a chosen model
survives across sessions.
"""

from __future__ import annotations

from pathlib import Path

from sage.config import GLOBAL_ENV_PATH


def set_env_var(key: str, value: str, path: Path | None = None) -> bool:
    """Set or update a KEY=value line in the global .env file.

    Preserves other lines. Creates the file/dir if missing.

    Args:
        key: The environment variable name (e.g. "MODEL").
        value: The value to set.
        path: Optional override path (defaults to GLOBAL_ENV_PATH).

    Returns:
        True on success, False on any I/O error.
    """
    target = path or GLOBAL_ENV_PATH
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        if target.is_file():
            lines = target.read_text(encoding="utf-8").splitlines()

        new_line = f"{key}={value}"
        replaced = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
                lines[i] = new_line
                replaced = True
                break
        if not replaced:
            lines.append(new_line)

        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False