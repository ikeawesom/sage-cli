# sage/tools.py
"""Tool implementations for the coding agent.

Each tool is a small, testable function operating within a sandbox.
Destructive tools (write_file, run_shell) require confirmation unless
auto-approve is enabled, and run_shell also enforces a deny-list of
dangerous commands.

Also exposes:
  - TOOL_SCHEMAS: native OpenAI tool schemas for the LLM.
  - ToolRegistry: dispatches tool calls to implementations.
"""

from __future__ import annotations

import difflib
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

from sage.confirm import Confirmer
from sage.sandbox import Sandbox, SandboxError
from sage.shell_safety import check_command

# Safety limits.
_MAX_READ_BYTES = 200_000
_MAX_OUTPUT_CHARS = 20_000
_SHELL_TIMEOUT = 60
_DIFF_MAX_LINES = 200  # cap diff lines shown in confirmation


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        ok: Whether the tool succeeded.
        output: Text output to feed back to the LLM.
    """

    ok: bool
    output: str


def _make_diff(old: str, new: str, path: str) -> str:
    """Produce a unified diff between old and new file contents.

    Args:
        old: Existing file contents (empty for new files).
        new: Proposed new contents.
        path: File path for the diff header.

    Returns:
        A unified-diff string (possibly truncated).
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{path}", tofile=f"b/{path}",
        )
    )
    if not diff:
        return "(no changes)"
    if len(diff) > _DIFF_MAX_LINES:
        diff = diff[:_DIFF_MAX_LINES] + [
            f"... [diff truncated at {_DIFF_MAX_LINES} lines] ...\n"
        ]
    return "".join(diff)


class Tools:
    """Concrete tool implementations bound to a sandbox + confirmer."""

    def __init__(self, sandbox: Sandbox, confirmer: Confirmer, mode_state) -> None:
        """Initialize tools.

        Args:
            sandbox: Path sandbox to confine file operations.
            confirmer: Confirmation handler for destructive actions.
            mode_state: Shared ModeState providing the active policy.
        """
        self.sandbox = sandbox
        self.confirmer = confirmer
        self.mode_state = mode_state

    # ── Read-only tools ───────────────────────────────────────────

    def read_file(self, path: str) -> ToolResult:
        """Read a UTF-8 text file within the sandbox.

        Refuses binary image/PDF files, guiding the model to use the
        attached visual input instead of reading raw bytes.

        Args:
            path: File path relative to the sandbox root.

        Returns:
            ToolResult with file contents or an error message.
        """
        try:
            target = self.sandbox.resolve(path)
        except SandboxError as exc:
            return ToolResult(False, f"Error: {exc}")

        if not target.is_file():
            return ToolResult(False, f"Error: '{path}' is not a file.")

        # Block binary image/PDF reads — these must come via /attach as
        # vision input, not raw bytes.
        binary_suffixes = {
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf",
        }
        if target.suffix.lower() in binary_suffixes:
            return ToolResult(
                False,
                f"Error: '{path}' is an image/PDF and cannot be read as text. "
                "If the user wants it analyzed, it must be attached as visual "
                "input via /attach; do not read its raw bytes.",
            )

        try:
            data = target.read_bytes()
            if len(data) > _MAX_READ_BYTES:
                data = data[:_MAX_READ_BYTES]
                truncated = f"\n\n[...truncated at {_MAX_READ_BYTES} bytes...]"
            else:
                truncated = ""
            text = data.decode("utf-8", errors="replace")
            return ToolResult(True, text + truncated)
        except OSError as exc:
            return ToolResult(False, f"Error reading '{path}': {exc}")

    def list_dir(self, path: str = ".") -> ToolResult:
        """List entries in a directory within the sandbox.

        Args:
            path: Directory path relative to the sandbox root.

        Returns:
            ToolResult with a listing (dirs marked with trailing '/').
        """
        try:
            target = self.sandbox.resolve(path)
        except SandboxError as exc:
            return ToolResult(False, f"Error: {exc}")

        if not target.is_dir():
            return ToolResult(False, f"Error: '{path}' is not a directory.")
        try:
            entries = sorted(target.iterdir(), key=lambda p: p.name)
            lines = [f"{e.name}/" if e.is_dir() else e.name for e in entries]
            listing = "\n".join(lines) if lines else "(empty)"
            return ToolResult(True, listing)
        except OSError as exc:
            return ToolResult(False, f"Error listing '{path}': {exc}")

    # ── Destructive tools (require confirmation) ──────────────────

    def write_file(self, path: str, content: str) -> ToolResult:
        """Write text to a file within the sandbox (per mode policy).

        Shows a unified diff of the proposed change before asking.

        Args:
            path: File path relative to the sandbox root.
            content: Full file contents to write.

        Returns:
            ToolResult indicating success or the reason for refusal.
        """
        policy = self.mode_state.policy
        if not policy.writes_allowed:
            return ToolResult(
                False,
                f"Blocked: file writes are disabled in '{policy.label}' mode. "
                "Describe the change instead.",
            )

        try:
            target = self.sandbox.resolve(path)
        except SandboxError as exc:
            return ToolResult(False, f"Error: {exc}")

        exists = target.is_file()
        old = ""
        if exists:
            try:
                old = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                old = ""

        verb = "Overwrite" if exists else "Create"
        rel = self.sandbox.relative(target)
        diff = _make_diff(old, content, rel)
        detail = (
            f"{verb} file: {rel}  ({len(content)} chars)\n"
            f"--- diff ---\n{diff}"
        )
        approved = self.confirmer.decide(
            f"{verb} file", detail, auto=policy.writes_auto, kind="diff"
        )
        if not approved:
            return ToolResult(False, "Write cancelled by user.")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(True, f"Wrote {len(content)} chars to '{path}'.")
        except OSError as exc:
            return ToolResult(False, f"Error writing '{path}': {exc}")

    def run_shell(self, command: str) -> ToolResult:
        """Run a shell command in the sandbox root (per mode policy).

        Enforces the deny-list unless the active mode disables it.

        Args:
            command: The shell command line to execute.

        Returns:
            ToolResult with combined stdout/stderr and exit code.
        """
        policy = self.mode_state.policy
        if not policy.shell_allowed:
            return ToolResult(
                False,
                f"Blocked: shell commands are disabled in '{policy.label}' mode. "
                "Describe what you would run instead.",
            )

        allow_dangerous = not policy.deny_list_enforced
        blocked = check_command(command, allow_dangerous)
        if blocked is not None:
            return ToolResult(
                False,
                f"Error: command blocked by safety policy ({blocked}). "
                "Not executed.",
            )

        detail = f"Command: {command}\nWorking dir: {self.sandbox.root}"
        approved = self.confirmer.decide(
            "Run shell command", detail, auto=policy.shell_auto
        )
        if not approved:
            return ToolResult(False, "Command cancelled by user.")

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.sandbox.root,
                capture_output=True,
                text=True,
                timeout=_SHELL_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, f"Command timed out after {_SHELL_TIMEOUT}s.")
        except OSError as exc:
            return ToolResult(False, f"Error running command: {exc}")

        combined = (proc.stdout or "") + (proc.stderr or "")
        if len(combined) > _MAX_OUTPUT_CHARS:
            combined = combined[:_MAX_OUTPUT_CHARS] + "\n[...output truncated...]"
        status = "ok" if proc.returncode == 0 else f"exit={proc.returncode}"
        output = f"[{status}]\n{combined}".rstrip()
        return ToolResult(proc.returncode == 0, output)

# ── Native tool schemas (unchanged from Phase 3) ─────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file in the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to root. Default '.'.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a text file. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file contents to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command in the project root. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command line to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
]


class ToolRegistry:
    """Maps tool names to implementations and dispatches calls."""

    def __init__(self, tools: Tools) -> None:
        """Initialize the registry.

        Args:
            tools: The concrete Tools instance to dispatch to.
        """
        self._dispatch: dict[str, Callable[..., ToolResult]] = {
            "read_file": tools.read_file,
            "list_dir": tools.list_dir,
            "write_file": tools.write_file,
            "run_shell": tools.run_shell,
        }

    def names(self) -> list[str]:
        """Return the list of registered tool names."""
        return list(self._dispatch)

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Dispatch a tool call by name with keyword arguments.

        Args:
            name: Tool name (must be registered).
            arguments: Keyword arguments parsed from the model.

        Returns:
            The ToolResult from the tool, or an error result if the
            tool is unknown or arguments are invalid.
        """
        func = self._dispatch.get(name)
        if func is None:
            return ToolResult(False, f"Error: unknown tool '{name}'.")
        try:
            return func(**arguments)
        except TypeError as exc:
            return ToolResult(False, f"Error: bad arguments for '{name}': {exc}")