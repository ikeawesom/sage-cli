# sage/attachments.py
"""Multimodal attachment support (images / PDFs) as base64 data URLs.

Builds OpenAI-style multimodal message content blocks so the user can
include images or PDFs with a request. Sandbox-checked paths.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from sage.sandbox import Sandbox, SandboxError

# Reasonable size cap to avoid oversized requests (~10 MB).
_MAX_ATTACH_BYTES = 10 * 1024 * 1024

_SUPPORTED = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


class AttachmentError(Exception):
    """Raised when an attachment cannot be prepared."""


def build_attachment_block(sandbox: Sandbox, path: str) -> dict[str, Any]:
    """Build a multimodal content block for one file.

    Args:
        sandbox: The active sandbox (for path safety).
        path: File path relative to the sandbox root.

    Returns:
        An OpenAI content block (image_url style with a data: URL).

    Raises:
        AttachmentError: If the file is missing, too large, or unsupported.
    """
    try:
        target = sandbox.resolve(path)
    except SandboxError as exc:
        raise AttachmentError(str(exc)) from exc

    if not target.is_file():
        raise AttachmentError(f"'{path}' is not a file.")

    suffix = target.suffix.lower()
    mime = _SUPPORTED.get(suffix) or mimetypes.guess_type(str(target))[0]
    if mime is None or suffix not in _SUPPORTED:
        raise AttachmentError(
            f"Unsupported attachment type '{suffix}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED))}"
        )

    data = target.read_bytes()
    if len(data) > _MAX_ATTACH_BYTES:
        raise AttachmentError(
            f"Attachment too large ({len(data)} bytes; "
            f"max {_MAX_ATTACH_BYTES})."
        )

    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    return {"type": "image_url", "image_url": {"url": data_url}}


def build_multimodal_message(
    sandbox: Sandbox, text: str, paths: list[str]
) -> dict[str, Any]:
    """Build a user message combining text and one or more attachments.

    Args:
        sandbox: The active sandbox.
        text: The user's text prompt.
        paths: Attachment file paths.

    Returns:
        A user message dict with a list content (text + attachments).

    Raises:
        AttachmentError: If any attachment fails to prepare.
    """
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for path in paths:
        content.append(build_attachment_block(sandbox, path))
    return {"role": "user", "content": content}