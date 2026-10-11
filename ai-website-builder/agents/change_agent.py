"""
Change Planner + Code Modification Agent.

Together these implement the "modify existing website" workflow:

    user modification request
            |
      Change Planner            -> decides which existing files are affected
            |
    Code Modification Agent     -> rewrites only those files
            |
      (Testing / Debugging reused from the main pipeline)
"""
from __future__ import annotations

import os

from core.llm import LLMProvider, get_structured_response
from core.models import ChangePlan, GeneratedFile, GeneratedFiles

_PLAN_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "change_plan.txt"
)
_MODIFY_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "code_modification.txt"
)


def _load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def plan_change(provider: LLMProvider, files: GeneratedFiles, modification_request: str) -> ChangePlan:
    system_prompt = _load(_PLAN_PROMPT_PATH)
    file_list = "\n".join(f"- {f.path}" for f in files.files)
    user_message = (
        f"Existing project files:\n{file_list}\n\n"
        f"User's modification request:\n\"\"\"\n{modification_request}\n\"\"\""
    )
    plan = get_structured_response(provider, system_prompt, user_message, ChangePlan, max_tokens=1024)

    # Guard against the LLM naming a file that doesn't actually exist.
    existing_paths = {f.path for f in files.files}
    plan.affected_files = [p for p in plan.affected_files if p in existing_paths]
    if not plan.affected_files:
        # Fall back to the most likely candidate rather than doing nothing.
        plan.affected_files = ["css/style.css"] if "css/style.css" in existing_paths else list(existing_paths)[:1]
    return plan


def apply_change(
    provider: LLMProvider, files: GeneratedFiles, affected_paths: list[str], modification_request: str
) -> GeneratedFiles:
    system_prompt = _load(_MODIFY_PROMPT_PATH)
    targeted = [f for f in files.files if f.path in affected_paths]
    files_dump = "\n\n".join(f"--- {f.path} ---\n{f.content}" for f in targeted)
    user_message = (
        f"User's modification request:\n\"\"\"\n{modification_request}\n\"\"\"\n\n"
        f"Files to modify:\n{files_dump}"
    )
    result = get_structured_response(provider, system_prompt, user_message, GeneratedFiles, max_tokens=8192)

    if not result.files:
        raise ValueError("Code Modification Agent returned no files")
    return result
