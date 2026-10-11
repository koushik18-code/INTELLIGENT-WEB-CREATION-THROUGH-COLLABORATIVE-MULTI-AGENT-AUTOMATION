"""Read-only provider/model info for the frontend. Never exposes key values —
only whether a key is configured, so the UI can gray out an unusable provider."""
from __future__ import annotations

import os

from core.llm import model_choices_for

PROVIDERS = ["mock", "anthropic", "openai", "gemini", "groq", "openrouter"]


def _has_real_key(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return bool(value) and not value.startswith("your_")


def list_providers() -> list[dict]:
    return [
        {
            "id": "mock",
            "label": "Mock (Offline)",
            "requires_api_key": False,
            "configured": True,
            "models": model_choices_for("mock"),
        },
        {
            "id": "anthropic",
            "label": "Anthropic",
            "requires_api_key": True,
            "configured": _has_real_key("ANTHROPIC_API_KEY"),
            "models": model_choices_for("anthropic"),
        },
        {
            "id": "openai",
            "label": "OpenAI",
            "requires_api_key": True,
            "configured": _has_real_key("OPENAI_API_KEY"),
            "models": model_choices_for("openai"),
        },
        {
            "id": "gemini",
            "label": "Google Gemini",
            "requires_api_key": True,
            "configured": _has_real_key("GEMINI_API_KEY"),
            "models": model_choices_for("gemini"),
        },
        {
            "id": "groq",
            "label": "Groq",
            "requires_api_key": True,
            "configured": _has_real_key("GROQ_API_KEY"),
            "models": model_choices_for("groq"),
        },
        {
            "id": "openrouter",
            "label": "OpenRouter",
            "requires_api_key": True,
            "configured": _has_real_key("OPENROUTER_API_KEY"),
            "models": model_choices_for("openrouter"),
        },
    ]
