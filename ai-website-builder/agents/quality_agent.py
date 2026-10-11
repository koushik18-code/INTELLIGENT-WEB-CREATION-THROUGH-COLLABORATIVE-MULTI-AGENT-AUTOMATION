"""Quality Agent: final holistic review before the site is presented."""
from __future__ import annotations

import os

from core.llm import LLMProvider, get_structured_response
from core.models import GeneratedFiles, QualityReport, Requirements, UIDesign

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "quality.txt")


def _load_system_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run(provider: LLMProvider, requirements: Requirements, design: UIDesign, files: GeneratedFiles) -> QualityReport:
    system_prompt = _load_system_prompt()
    files_summary = "\n\n".join(f"--- {f.path} ---\n{f.content[:3000]}" for f in files.files)
    user_message = (
        f"Requirements specification (JSON):\n{requirements.model_dump_json(indent=2)}\n\n"
        f"UI/UX design specification (JSON):\n{design.model_dump_json(indent=2)}\n\n"
        f"Final project files:\n{files_summary}"
    )
    return get_structured_response(provider, system_prompt, user_message, QualityReport, max_tokens=2048)
