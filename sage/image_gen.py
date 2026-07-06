# sage/image_gen.py
"""Image generation via the OpenAI-compatible images API.

The endpoint returns base64-encoded PNGs (b64_json). This module
requests an image, decodes it, saves it into the sandbox, and returns
the saved path. Falls back to lighter image models if the primary
model errors (e.g. temporarily unavailable).
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from sage.config import Config
from sage.http import build_http_client
from sage.sandbox import Sandbox

# Primary first; used as automatic fallbacks if the primary errors.
DEFAULT_IMAGE_MODEL = "gemini-3-pro-image"
FALLBACK_IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
]


class ImageGenError(Exception):
    """Raised when image generation fails on all attempted models."""


@dataclass
class ImageResult:
    """Result of a successful image generation.

    Attributes:
        path: Absolute path to the saved image file.
        model_used: The model that actually produced the image.
    """

    path: Path
    model_used: str


class ImageGenerator:
    """Generates images and saves them into a sandbox directory."""

    def __init__(self, config: Config, sandbox: Sandbox) -> None:
        """Initialize the generator.

        Args:
            config: Application config (for API credentials/TLS).
            sandbox: Sandbox to save images within.
        """
        self._config = config
        self._sandbox = sandbox
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            http_client=build_http_client(config),
        )

    def _models_to_try(self, primary: str) -> list[str]:
        """Return an ordered, de-duplicated list of models to attempt."""
        ordered = [primary] + [
            m for m in FALLBACK_IMAGE_MODELS if m != primary
        ]
        return ordered

    def _next_filename(self, stem: str = "sage-image") -> Path:
        """Pick a non-colliding output path within the sandbox root.

        Args:
            stem: Base filename stem.

        Returns:
            An available Path like <root>/sage-image-1.png.
        """
        i = 1
        while True:
            candidate = self._sandbox.root / f"{stem}-{i}.png"
            if not candidate.exists():
                return candidate
            i += 1

    def generate(
        self, prompt: str, *, model: str = DEFAULT_IMAGE_MODEL
    ) -> ImageResult:
        """Generate an image and save it as a PNG in the sandbox.

        Args:
            prompt: The text prompt describing the image.
            model: Preferred image model (falls back on error).

        Returns:
            An ImageResult with the saved path and model used.

        Raises:
            ImageGenError: If all models fail.
        """
        errors: list[str] = []
        for candidate in self._models_to_try(model):
            try:
                b64 = self._request_b64(candidate, prompt)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
                continue

            if not b64:
                errors.append(f"{candidate}: empty image data")
                continue

            path = self._next_filename()
            try:
                path.write_bytes(base64.b64decode(b64))
            except (OSError, ValueError) as exc:
                errors.append(f"{candidate}: save failed: {exc}")
                continue
            return ImageResult(path=path, model_used=candidate)

        raise ImageGenError(
            "Image generation failed on all models:\n  " + "\n  ".join(errors)
        )

    def _request_b64(self, model: str, prompt: str) -> str | None:
        """Call images.generate and extract base64 PNG data.

        Args:
            model: The image model ID.
            prompt: The text prompt.

        Returns:
            The b64_json string, or None if absent.
        """
        resp = self._client.images.generate(model=model, prompt=prompt, n=1)
        if not resp.data:
            return None
        item: Any = resp.data[0]
        return getattr(item, "b64_json", None)


def open_file(path: Path) -> None:
    """Open a file with the OS default application.

    Best-effort; failures are silent (the path is always printed too).

    Args:
        path: File to open.
    """
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]  # Windows
        elif os.name == "posix":
            import subprocess

            opener = "open" if _is_macos() else "xdg-open"
            subprocess.Popen(
                [opener, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:  # noqa: BLE001
        pass  # non-fatal; user still has the printed path


def _is_macos() -> bool:
    """Return True if running on macOS."""
    import sys

    return sys.platform == "darwin"