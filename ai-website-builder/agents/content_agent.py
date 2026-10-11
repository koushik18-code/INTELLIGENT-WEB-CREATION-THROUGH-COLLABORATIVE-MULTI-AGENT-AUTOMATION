"""Content Agent: writes realistic copy for every section of the site."""
from __future__ import annotations

import os

from core.llm import LLMProvider, get_structured_response
from core.models import Content, Requirements, UIDesign

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "content.txt")


def _load_system_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run(provider: LLMProvider, user_prompt: str, requirements: Requirements, design: UIDesign) -> Content:
    system_prompt = _load_system_prompt()
    user_message = (
        f"Original user prompt:\n\"\"\"\n{user_prompt}\n\"\"\"\n\n"
        f"Requirements specification (JSON):\n{requirements.model_dump_json(indent=2)}\n\n"
        f"UI/UX design specification (JSON):\n{design.model_dump_json(indent=2)}"
    )
    return get_structured_response(provider, system_prompt, user_message, Content)
