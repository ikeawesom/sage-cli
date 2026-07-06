# sage/models_catalog.py
"""Curated catalog of chat models available to Sage.

Only hand-picked, high-quality chat models are exposed via /model.
Image-generation models are intentionally excluded here (they use a
different API and will be handled by a dedicated /image command later).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    """Metadata for a selectable chat model.

    Attributes:
        model_id: Exact model ID passed to the API.
        label: Short display name.
        category: Grouping ("coding", "fast").
        note: One-line description.
    """

    model_id: str
    label: str
    category: str
    note: str


# Curated, ordered list. Index in /model corresponds to position here.
CHAT_MODELS: list[ModelInfo] = [
    # ── General purpose (most capable) ──
    ModelInfo(
        "claude-opus-4-8", "Claude Opus 4.8", "general",
        "Most capable all-rounder; best for complex analysis (default).",
    ),
    ModelInfo(
        "claude-sonnet-4-6", "Claude Sonnet 4.6", "general",
        "Fast and highly capable; great balance of speed and quality.",
    ),
    ModelInfo(
        "claude-opus-4-5-20251101", "Claude Opus 4.5", "general",
        "Very strong reasoning for detailed, multi-step tasks.",
    ),
    ModelInfo(
        "gemini-3-pro", "Gemini 3 Pro", "general",
        "Strong reasoning; handles very large documents well.",
    ),
    ModelInfo(
        "GPT5-chat", "GPT-5 Chat", "general",
        "OpenAI's GPT-5; versatile general-purpose assistant.",
    ),
    # ── Fast / lightweight ──
    ModelInfo(
        "claude-haiku-4-5-20251001", "Claude Haiku 4.5", "fast",
        "Quick responses for simple questions; low cost.",
    ),
    ModelInfo(
        "gemini-3-flash", "Gemini 3 Flash", "fast",
        "Very fast; good for quick lookups and short tasks.",
    ),
]


def find_by_id(model_id: str) -> ModelInfo | None:
    """Return the ModelInfo matching a model ID, or None.

    Args:
        model_id: Exact model ID.

    Returns:
        The matching ModelInfo or None.
    """
    for m in CHAT_MODELS:
        if m.model_id == model_id:
            return m
    return None


def get_by_index(index: int) -> ModelInfo | None:
    """Return the ModelInfo at a 1-based index, or None if out of range.

    Args:
        index: 1-based position in CHAT_MODELS.

    Returns:
        The matching ModelInfo or None.
    """
    if 1 <= index <= len(CHAT_MODELS):
        return CHAT_MODELS[index - 1]
    return None