"""UI/UX Agent: turns Requirements into a detailed UIDesign spec."""
from __future__ import annotations

import os

from core.llm import LLMProvider, get_structured_response
from core.models import Requirements, UIDesign

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "ui_ux.txt")


def _load_system_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run(provider: LLMProvider, user_prompt: str, requirements: Requirements) -> UIDesign:
    system_prompt = _load_system_prompt()
    user_message = (
        f"Original user prompt:\n\"\"\"\n{user_prompt}\n\"\"\"\n\n"
        f"Requirements specification (JSON):\n{requirements.model_dump_json(indent=2)}"
    )
    return get_structured_response(provider, system_prompt, user_message, UIDesign)
