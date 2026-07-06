# sage/modes.py
"""Operating modes for the agent (Plan / Normal / Auto-edits / Auto / Bypass).

Each mode maps to a ModePolicy describing what the tools are allowed to
do and whether actions are auto-approved. The policy is consulted at
runtime by the Confirmer/Tools, so switching modes takes effect
immediately without rebuilding anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    """Available operating modes."""

    PLAN = "plan"
    NORMAL = "normal"
    AUTO_EDITS = "auto-edits"
    AUTO = "auto"
    BYPASS = "bypass"

    @classmethod
    def from_str(cls, value: str) -> "Mode":
        """Parse a mode name (case-insensitive, tolerant of underscores).

        Args:
            value: The mode name string.

        Returns:
            The matching Mode.

        Raises:
            ValueError: If the name is not a valid mode.
        """
        norm = value.strip().lower().replace("_", "-")
        for mode in cls:
            if mode.value == norm:
                return mode
        valid = ", ".join(m.value for m in cls)
        raise ValueError(f"Unknown mode '{value}'. Valid: {valid}")


@dataclass(frozen=True)
class ModePolicy:
    """Permissions and auto-approval rules for a mode.

    Attributes:
        writes_allowed: Whether write_file may run at all.
        writes_auto: If True, writes are auto-approved (no prompt).
        shell_allowed: Whether run_shell may run at all.
        shell_auto: If True, shell commands are auto-approved.
        deny_list_enforced: Whether the shell deny-list applies.
        plan_note: Optional system guidance injected in this mode.
        label: Short human label.
        color: Rich color for UI display.
    """

    writes_allowed: bool
    writes_auto: bool
    shell_allowed: bool
    shell_auto: bool
    deny_list_enforced: bool
    plan_note: str
    label: str
    color: str


_PLAN_NOTE = (
    "You are currently in PLAN MODE. Investigate the project using read-only "
    "tools (read_file, list_dir) and produce a clear, step-by-step plan of the "
    "changes you WOULD make. Do NOT attempt to write files or run shell "
    "commands — those tools are disabled in this mode. End with a concise "
    "numbered plan the user can approve."
)


_POLICIES: dict[Mode, ModePolicy] = {
    Mode.PLAN: ModePolicy(
        writes_allowed=False,
        writes_auto=False,
        shell_allowed=False,
        shell_auto=False,
        deny_list_enforced=True,
        plan_note=_PLAN_NOTE,
        label="plan",
        color="magenta",
    ),
    Mode.NORMAL: ModePolicy(
        writes_allowed=True,
        writes_auto=False,
        shell_allowed=True,
        shell_auto=False,
        deny_list_enforced=True,
        plan_note="",
        label="normal",
        color="green",
    ),
    Mode.AUTO_EDITS: ModePolicy(
        writes_allowed=True,
        writes_auto=True,
        shell_allowed=True,
        shell_auto=False,
        deny_list_enforced=True,
        plan_note="",
        label="auto-edits",
        color="cyan",
    ),
    Mode.AUTO: ModePolicy(
        writes_allowed=True,
        writes_auto=True,
        shell_allowed=True,
        shell_auto=True,
        deny_list_enforced=True,  # safety net stays on
        plan_note="",
        label="auto",
        color="yellow",
    ),
    Mode.BYPASS: ModePolicy(
        writes_allowed=True,
        writes_auto=True,
        shell_allowed=True,
        shell_auto=True,
        deny_list_enforced=False,  # deny-list OFF — maximum danger
        plan_note="",
        label="bypass",
        color="red",
    ),
}


def policy_for(mode: Mode) -> ModePolicy:
    """Return the ModePolicy for a given Mode.

    Args:
        mode: The operating mode.

    Returns:
        The associated ModePolicy.
    """
    return _POLICIES[mode]


class ModeState:
    """Holds the current mode; shared (by reference) across components.

    Because Tools/Confirmer keep a reference to this object, changing the
    mode here is immediately visible everywhere.
    """

    def __init__(self, mode: Mode = Mode.NORMAL) -> None:
        """Initialize with a starting mode.

        Args:
            mode: The initial operating mode.
        """
        self._mode = mode

    @property
    def mode(self) -> Mode:
        """The current mode."""
        return self._mode

    @property
    def policy(self) -> ModePolicy:
        """The current mode's policy."""
        return policy_for(self._mode)

    def set(self, mode: Mode) -> None:
        """Switch to a new mode.

        Args:
            mode: The mode to activate.
        """
        self._mode = mode