# sage/confirm.py
"""Interactive confirmation for destructive actions.

Consults the active ModeState policy to decide whether an action is
blocked, auto-approved, or requires an interactive prompt. Renders
unified diffs with color when the detail is a diff.
"""

from __future__ import annotations

from rich.console import Console
from rich.syntax import Syntax

from sage.modes import ModeState


class Confirmer:
    """Prompts (or auto-approves/blocks) destructive actions per mode.

    Attributes:
        mode_state: Shared mode holder driving approval behavior.
        console: Rich console for formatted output.
    """

    def __init__(self, mode_state: ModeState, console: Console | None = None) -> None:
        """Initialize the confirmer.

        Args:
            mode_state: Shared ModeState (approval policy source).
            console: Optional rich Console (created if not provided).
        """
        self.mode_state = mode_state
        self.console = console or Console()

    def decide(self, action: str, detail: str, *, auto: bool, kind: str = "text") -> bool:
        """Approve an action given an auto flag from the caller's policy.

        Args:
            action: Short description (e.g. "Write file").
            detail: Extra context. If kind=="diff", the part after the
                "--- diff ---" marker is syntax-highlighted.
            auto: If True, auto-approve without prompting.
            kind: "text" or "diff" — controls rendering.

        Returns:
            True if approved, False otherwise.
        """
        if auto:
            self.console.print(f"[dim][auto][/] {action}")
            self._render_detail(detail, kind)
            return True

        self.console.print(f"\n[bold yellow]⚠  {action}[/]")
        self._render_detail(detail, kind)
        try:
            answer = self.console.input("[bold]Proceed?[/] [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            self.console.print()
            return False
        return answer in {"y", "yes"}

    def _render_detail(self, detail: str, kind: str) -> None:
        """Render the detail block, highlighting diffs when applicable.

        Args:
            detail: The detail text.
            kind: "text" or "diff".
        """
        if kind == "diff" and "--- diff ---" in detail:
            header, _, diff_body = detail.partition("--- diff ---")
            if header.strip():
                self.console.print(header.strip())
            syntax = Syntax(
                diff_body.strip("\n"), "diff", theme="ansi_dark", word_wrap=True
            )
            self.console.print(syntax)
        elif detail:
            self.console.print(detail)