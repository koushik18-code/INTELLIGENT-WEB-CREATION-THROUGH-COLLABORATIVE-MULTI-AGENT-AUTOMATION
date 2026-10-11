"""Requirements Agent: turns the raw user prompt into a Requirements spec."""
from __future__ import annotations

import os

from core.llm import LLMProvider, get_structured_response
from core.models import Requirements

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "requirements.txt")


def _load_system_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run(provider: LLMProvider, user_prompt: str) -> Requirements:
    system_prompt = _load_system_prompt()
    user_message = f"User's website request:\n\n\"\"\"\n{user_prompt}\n\"\"\""
    return get_structured_response(provider, system_prompt, user_message, Requirements)
