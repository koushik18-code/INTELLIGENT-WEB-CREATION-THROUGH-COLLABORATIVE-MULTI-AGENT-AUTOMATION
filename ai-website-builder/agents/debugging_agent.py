"""Debugging Agent: applies the smallest fix for reported test errors."""
from __future__ import annotations

import os

from core.llm import LLMProvider, get_structured_response
from core.models import DebugResult, GeneratedFiles, TestResults

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "debugging.txt")


def _load_system_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run(provider: LLMProvider, files: GeneratedFiles, test_results: TestResults) -> DebugResult:
    system_prompt = _load_system_prompt()
    files_dump = "\n\n".join(f"--- {f.path} ---\n{f.content}" for f in files.files)
    user_message = (
        f"Errors reported by the Testing Agent:\n" + "\n".join(f"- {e}" for e in test_results.errors) + "\n\n"
        f"Warnings (fix opportunistically only if trivial, do not over-reach):\n"
        + "\n".join(f"- {w}" for w in test_results.warnings) + "\n\n"
        f"Current project files:\n{files_dump}"
    )
    return get_structured_response(provider, system_prompt, user_message, DebugResult, max_tokens=8192)
