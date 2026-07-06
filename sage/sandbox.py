# sage/sandbox.py
"""Path sandboxing utilities.

Ensures all file operations stay within an allowed root directory
(the current working directory by default), preventing path-escape
attacks like '../../etc/passwd'.
"""

from __future__ import annotations

from pathlib import Path


class SandboxError(Exception):
    """Raised when a path escapes the sandbox root."""


class Sandbox:
    """Confines path operations to a root directory.

    Attributes:
        root: The absolute, resolved sandbox root.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        """Initialize the sandbox.

        Args:
            root: Root directory. Defaults to the current working dir.
        """
        self.root = Path(root or Path.cwd()).resolve()

    def resolve(self, relative_path: str) -> Path:
        """Resolve a user-supplied path against the sandbox root.

        Args:
            relative_path: A path (relative or absolute) from the caller.

        Returns:
            The resolved absolute Path, guaranteed within the root.

        Raises:
            SandboxError: If the resolved path escapes the root.
        """
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise SandboxError(
                f"Path '{relative_path}' escapes sandbox root '{self.root}'."
            )
        return candidate

    def relative(self, path: Path) -> str:
        """Return a path as a string relative to the sandbox root."""
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)