"""Code Generation Agent: produces the full set of website files."""
from __future__ import annotations

import os

from core.llm import LLMProvider, get_structured_response
from core.models import Architecture, Content, GeneratedFiles, Requirements, UIDesign

_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "code_generation.txt"
)


def _load_system_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run(
    provider: LLMProvider,
    requirements: Requirements,
    design: UIDesign,
    architecture: Architecture,
    content: Content,
) -> GeneratedFiles:
    system_prompt = _load_system_prompt()
    user_message = (
        f"Requirements specification (JSON):\n{requirements.model_dump_json(indent=2)}\n\n"
        f"UI/UX design specification (JSON):\n{design.model_dump_json(indent=2)}\n\n"
        f"Architecture plan (JSON):\n{architecture.model_dump_json(indent=2)}\n\n"
        f"Content (JSON):\n{content.model_dump_json(indent=2)}"
    )
    result = get_structured_response(provider, system_prompt, user_message, GeneratedFiles, max_tokens=8192)

    if not result.files:
        raise ValueError("Code Generation Agent returned zero files")
    if not any(f.path == "index.html" for f in result.files):
        raise ValueError("Code Generation Agent did not produce an index.html")

    return result
