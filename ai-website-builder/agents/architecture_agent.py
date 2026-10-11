"""Architecture Agent: decides file structure and technical approach."""
from __future__ import annotations

import os

from core.llm import LLMProvider, get_structured_response
from core.models import Architecture, Requirements, UIDesign

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "architecture.txt")


def _load_system_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run(provider: LLMProvider, requirements: Requirements, design: UIDesign) -> Architecture:
    system_prompt = _load_system_prompt()
    user_message = (
        f"Requirements specification (JSON):\n{requirements.model_dump_json(indent=2)}\n\n"
        f"UI/UX design specification (JSON):\n{design.model_dump_json(indent=2)}"
    )
    return get_structured_response(provider, system_prompt, user_message, Architecture)
