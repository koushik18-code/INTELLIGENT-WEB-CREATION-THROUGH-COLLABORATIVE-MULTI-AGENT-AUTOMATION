"""
Bridges the HTTP API to the existing, UI-agnostic core.app_service layer.

    FastAPI routes -> ProjectSession (this module) -> core.app_service
                                                     -> Orchestrator -> Agents

Nothing about the AI pipeline changes here: this module only adds an
in-memory project registry, a background thread per generation/modification
run, and a per-project event queue so the HTTP layer can stream live
progress (SSE) the same way the Gradio UI polled a queue in-process.
"""
from __future__ import annotations

import queue
import threading
import time
import uuid
from typing import Optional

from core import app_service
from core.file_manager import cleanup_project as _cleanup_project_files
from core.state import ProjectState

MAX_LOG_LINES = 300


class ProjectNotFound(Exception):
    pass


class GenerationInProgress(Exception):
    pass


class ProjectSession:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.state: Optional[ProjectState] = None
        self.lock = threading.Lock()
        self.event_queue: "queue.Queue" = queue.Queue()
        self.cancel_event: threading.Event = threading.Event()
        self.busy: bool = False
        self.last_error: Optional[str] = None


_sessions: dict[str, ProjectSession] = {}
_registry_lock = threading.Lock()


def create_project() -> str:
    project_id = uuid.uuid4().hex[:12]
    with _registry_lock:
        _sessions[project_id] = ProjectSession(project_id)
    return project_id


def get_session(project_id: str) -> ProjectSession:
    session = _sessions.get(project_id)
    if session is None:
        raise ProjectNotFound(project_id)
    return session


def reset_project(project_id: str) -> None:
    """Delete a project's generated files and drop its in-memory session."""
    with _registry_lock:
        _sessions.pop(project_id, None)
    _cleanup_project_files(project_id)


def summarize_state(state: Optional[ProjectState]) -> dict:
    if state is None:
        return {"status": "idle"}
    return {
        "project_id": state.project_id,
        "status": state.status.value,
        "quality_score": state.quality_report.score if state.quality_report else None,
        "quality_recommendations": state.quality_report.recommendations if state.quality_report else [],
        "files_count": len(state.files.files) if state.files else 0,
        "tests_passed": state.test_results.passed if state.test_results else None,
        "test_errors": state.test_results.errors if state.test_results else [],
        "test_warnings": state.test_results.warnings if state.test_results else [],
        "debug_iterations": state.iteration,
        "elapsed_seconds": state.elapsed_seconds(),
        "provider": state.provider_name,
        "model": state.model_name,
        "errors": state.errors,
        "logs": [
            {"timestamp": e.timestamp, "agent": e.agent, "message": e.message}
            for e in state.agent_logs[-MAX_LOG_LINES:]
        ],
    }


def _run_in_background(session: ProjectSession, target) -> None:
    session.busy = True
    session.last_error = None
    session.cancel_event = threading.Event()
    # Drain any stale events from a previous run before starting a new one.
    while not session.event_queue.empty():
        try:
            session.event_queue.get_nowait()
        except queue.Empty:
            break

    def progress_cb(step: str, status: str) -> None:
        session.event_queue.put({"type": "progress", "step": step, "status": status, "ts": time.time()})

    def worker() -> None:
        try:
            state = target(progress_cb, session.cancel_event)
            with session.lock:
                session.state = state
            session.event_queue.put({"type": "done", "summary": summarize_state(state), "ts": time.time()})
        except Exception as e:  # noqa: BLE001 - surfaced to the client, never crashes the server
            session.last_error = str(e)
            session.event_queue.put({"type": "error", "message": str(e), "ts": time.time()})
        finally:
            session.busy = False

    threading.Thread(target=worker, daemon=True).start()


def start_generation(
    project_id: str,
    prompt: str,
    provider: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
) -> None:
    session = get_session(project_id)
    if session.busy:
        raise GenerationInProgress(project_id)

    def target(progress_cb, cancel_event):
        return app_service.generate_website(
            prompt, provider, model=model, temperature=temperature,
            on_progress=progress_cb, cancel_event=cancel_event, project_id=project_id,
        )

    _run_in_background(session, target)


def start_modification(
    project_id: str,
    modification_request: str,
    provider: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
) -> None:
    session = get_session(project_id)
    if session.busy:
        raise GenerationInProgress(project_id)
    if session.state is None:
        raise ValueError("Generate a website first before requesting changes.")

    def target(progress_cb, cancel_event):
        return app_service.modify_website(
            session.state, modification_request, provider, model=model, temperature=temperature,
            on_progress=progress_cb, cancel_event=cancel_event,
        )

    _run_in_background(session, target)


def cancel(project_id: str) -> None:
    session = get_session(project_id)
    session.cancel_event.set()
