from __future__ import annotations

import asyncio
import dataclasses
import json
import queue
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.services import project_service, providers_service
from core.file_manager import FileManagerError, list_file_tree

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
# Request bodies
# --------------------------------------------------------------------------- #
class GenerateRequest(BaseModel):
    prompt: str
    provider: str = "mock"
    model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=8192, ge=256, le=32768)
    website_type: Optional[str] = None
    visual_style: Optional[str] = None
    colors: Optional[str] = None
    audience: Optional[str] = None


class ModifyRequest(BaseModel):
    request: str
    provider: str = "mock"
    model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)


# --------------------------------------------------------------------------- #
# Health / providers
# --------------------------------------------------------------------------- #
@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/providers")
def get_providers():
    return {"providers": providers_service.list_providers()}


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #
@router.post("/projects")
def create_project():
    project_id = project_service.create_project()
    return {"project_id": project_id}


def _compose_prompt(body: GenerateRequest) -> str:
    """Fold the structured builder fields into one natural-language prompt for
    the Requirements Agent, without changing the agent's expected input shape."""
    parts = [body.prompt.strip()]
    if body.website_type:
        parts.append(f"Website type: {body.website_type}.")
    if body.visual_style:
        parts.append(f"Visual style: {body.visual_style}.")
    if body.colors:
        parts.append(f"Preferred colors: {body.colors}.")
    if body.audience:
        parts.append(f"Target audience: {body.audience}.")
    return " ".join(p for p in parts if p)


@router.post("/projects/{project_id}/generate")
def generate(project_id: str, body: GenerateRequest):
    try:
        project_service.start_generation(
            project_id,
            _compose_prompt(body),
            body.provider,
            body.model,
            body.temperature,
        )
    except project_service.ProjectNotFound:
        raise HTTPException(404, "Project not found")
    except project_service.GenerationInProgress:
        raise HTTPException(409, "Generation already in progress for this project")
    return {"status": "started"}


@router.post("/projects/{project_id}/modify")
def modify(project_id: str, body: ModifyRequest):
    try:
        project_service.start_modification(project_id, body.request, body.provider, body.model, body.temperature)
    except project_service.ProjectNotFound:
        raise HTTPException(404, "Project not found")
    except project_service.GenerationInProgress:
        raise HTTPException(409, "A generation or modification is already in progress")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "started"}


@router.post("/projects/{project_id}/cancel")
def cancel(project_id: str):
    try:
        project_service.cancel(project_id)
    except project_service.ProjectNotFound:
        raise HTTPException(404, "Project not found")
    return {"status": "cancelling"}


@router.post("/projects/{project_id}/reset")
def reset(project_id: str):
    project_service.reset_project(project_id)
    return {"status": "reset"}


@router.get("/projects/{project_id}/status")
def status(project_id: str):
    try:
        session = project_service.get_session(project_id)
    except project_service.ProjectNotFound:
        raise HTTPException(404, "Project not found")
    with session.lock:
        summary = project_service.summarize_state(session.state)
    summary["busy"] = session.busy
    return summary


@router.get("/projects/{project_id}/events")
async def events(project_id: str):
    """Server-Sent Events stream of live generation/modification progress.
    Falls back gracefully: a client that can't use SSE can just poll
    /status instead — both read from the same underlying session."""
    try:
        session = project_service.get_session(project_id)
    except project_service.ProjectNotFound:
        raise HTTPException(404, "Project not found")

    async def event_stream():
        # Send an initial snapshot immediately so a newly-connected client
        # (including one that reconnects mid-generation) isn't left blank.
        with session.lock:
            initial = project_service.summarize_state(session.state)
        initial["busy"] = session.busy
        yield f"data: {json.dumps({'type': 'snapshot', 'summary': initial})}\n\n"

        while True:
            try:
                event = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: session.event_queue.get(timeout=1.0)
                )
            except queue.Empty:
                if session.busy:
                    yield ": heartbeat\n\n"
                    continue
                break
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in ("done", "error"):
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/projects/{project_id}/files")
def files(project_id: str):
    try:
        tree = list_file_tree(project_id)
    except FileManagerError as e:
        raise HTTPException(400, str(e))
    return dataclasses.asdict(tree)


def _guess_language(path: str) -> Optional[str]:
    ext_map = {
        ".html": "html", ".htm": "html", ".css": "css", ".js": "javascript",
        ".json": "json", ".md": "markdown", ".txt": "plaintext",
    }
    for ext, lang in ext_map.items():
        if path.endswith(ext):
            return lang
    return None


@router.get("/projects/{project_id}/files/{path:path}")
def file_content(project_id: str, path: str):
    from core.app_service import get_file_content

    try:
        content = get_file_content(project_id, path)
    except Exception as e:  # security / not-found errors from file_manager
        raise HTTPException(404, str(e))
    return {"path": path, "content": content, "language": _guess_language(path)}


@router.get("/projects/{project_id}/preview")
def preview(project_id: str):
    from core.app_service import get_preview_html

    html = get_preview_html(project_id)
    return {"html": html}


@router.get("/projects/{project_id}/export")
def export(project_id: str):
    from core.app_service import get_zip_path

    try:
        zip_path = get_zip_path(project_id)
    except Exception as e:
        raise HTTPException(400, str(e))
    return FileResponse(zip_path, filename=f"{project_id}.zip", media_type="application/zip")
