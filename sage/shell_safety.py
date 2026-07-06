# sage/shell_safety.py
"""Shell command safety checks.

Blocks obviously destructive commands even in --auto mode, unless the
user explicitly allows them via config. Deny rules take precedence.
"""

from __future__ import annotations

import re

# Patterns considered dangerous. Case-insensitive, matched anywhere.
# Kept intentionally conservative to avoid false negatives.
_DENY_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-\w*r\w*f", "recursive force delete (rm -rf)"),
    (r"\brm\s+-\w*f\w*r", "recursive force delete (rm -fr)"),
    (r"\bdel\s+/[sfq]", "Windows recursive/force delete (del /s /f /q)"),
    (r"\brmdir\s+/s", "Windows recursive rmdir (rmdir /s)"),
    (r"\bformat\b", "disk format"),
    (r"\bmkfs\b", "filesystem creation (mkfs)"),
    (r"\bdd\b.*\bof=/dev/", "raw disk write (dd of=/dev/...)"),
    (r":\(\)\s*\{\s*:\|:&\s*\}\s*;", "fork bomb"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "system power control"),
    (r">\s*/dev/sd", "write to raw disk device"),
    (r"\bchmod\s+-R\s+777\b", "recursive world-writable chmod"),
    (r"\bgit\s+push\b.*--force", "force push"),
    (r"\bcurl\b.*\|\s*(sh|bash)\b", "pipe remote script to shell"),
    (r"\bwget\b.*\|\s*(sh|bash)\b", "pipe remote script to shell"),
]


class ShellSafetyError(Exception):
    """Raised when a command matches a deny rule."""


def check_command(command: str, allow_dangerous: bool = False) -> str | None:
    """Check a command against deny rules.

    Args:
        command: The shell command line.
        allow_dangerous: If True, bypass deny rules (explicit opt-in).

    Returns:
        None if allowed, or a human-readable reason string if blocked.
    """
    if allow_dangerous:
        return None
    lowered = command.strip()
    for pattern, reason in _DENY_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return reason
    return None