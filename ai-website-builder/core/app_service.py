"""
Application Service layer.

    UI (Gradio) -> Application Service (this module) -> Orchestrator -> Agents -> LLM Provider

Keeps app.py a thin UI-wiring file: it never talks to agents or the LLM
provider directly, only to the functions in here.
"""
from __future__ import annotations

from typing import Optional

from agents.orchestrator import Orchestrator, ProgressCallback
from core.file_manager import (
    build_zip,
    get_index_html_path,
    list_file_paths,
    read_file,
)
from core.llm import LLMConfigError, get_provider
from core.state import ProjectState

_provider_cache: dict[tuple, object] = {}


def get_configured_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
):
    """
    Instantiate the configured LLM provider, surfacing a clear, user-facing
    error message if required configuration (e.g. an API key) is missing.
    Cached per (provider, model, temperature) so switching any of the three
    in the UI takes effect immediately without restarting the app, while
    repeated calls with identical settings reuse the same client.
    """
    key = (provider_name or "default", model or "default", temperature)
    if key not in _provider_cache:
        _provider_cache[key] = get_provider(provider_name, model=model, temperature=temperature)
    return _provider_cache[key]


def generate_website(
    user_prompt: str,
    provider_name: Optional[str],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    on_progress: ProgressCallback = None,
    cancel_event=None,
    project_id: Optional[str] = None,
) -> ProjectState:
    if not user_prompt or not user_prompt.strip():
        raise ValueError("Please describe the website you want before generating.")
    provider = get_configured_provider(provider_name, model=model, temperature=temperature)
    orchestrator = Orchestrator(provider)
    return orchestrator.run(
        user_prompt.strip(), on_progress=on_progress, cancel_event=cancel_event, project_id=project_id
    )


def modify_website(
    state: ProjectState,
    modification_request: str,
    provider_name: Optional[str],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    on_progress: ProgressCallback = None,
    cancel_event=None,
) -> ProjectState:
    if not state or not state.files.files:
        raise ValueError("Generate a website first before requesting changes.")
    if not modification_request or not modification_request.strip():
        raise ValueError("Please describe the change you want before applying it.")
    provider = get_configured_provider(provider_name, model=model, temperature=temperature)
    orchestrator = Orchestrator(provider)
    return orchestrator.modify(state, modification_request.strip(), on_progress=on_progress, cancel_event=cancel_event)


def get_file_choices(project_id: str) -> list[str]:
    return list_file_paths(project_id)


def get_file_content(project_id: str, path: str) -> str:
    return read_file(project_id, path)


def get_zip_path(project_id: str) -> str:
    return build_zip(project_id)


def get_preview_html(project_id: str) -> str:
    """
    Build a self-contained preview document: inline the referenced local
    CSS/JS into index.html's markup so it can be shown inside a sandboxed
    iframe via srcdoc without needing to serve files over HTTP. The files
    written to disk / included in the ZIP are left untouched.
    """
    from bs4 import BeautifulSoup

    index_path = get_index_html_path(project_id)
    if not index_path:
        return "<p style='font-family:sans-serif;padding:2rem;'>No preview available yet.</p>"

    all_paths = set(get_file_choices(project_id))
    html = read_file(project_id, "index.html")
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("link", rel="stylesheet", href=True):
        href = link["href"]
        normalized = href.lstrip("./")
        if normalized in all_paths:
            style_tag = soup.new_tag("style")
            style_tag.string = read_file(project_id, normalized)
            link.replace_with(style_tag)

    for script in soup.find_all("script", src=True):
        src = script["src"]
        normalized = src.lstrip("./")
        if normalized in all_paths:
            inline_script = soup.new_tag("script")
            inline_script.string = read_file(project_id, normalized)
            script.replace_with(inline_script)

    return str(soup)
