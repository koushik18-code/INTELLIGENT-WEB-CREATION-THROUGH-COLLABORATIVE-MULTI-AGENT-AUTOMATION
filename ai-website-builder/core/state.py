"""
The single shared state object that flows through the whole pipeline.

Every agent reads from and writes to a `ProjectState` instance. Agents never
talk to each other directly — the Orchestrator is the only thing that
mutates state and decides what runs next. This keeps the workflow
controlled and inspectable instead of allowing free-form agent chatter.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.models import (
    Architecture,
    Content,
    GeneratedFiles,
    ProjectStatus,
    QualityReport,
    Requirements,
    TestResults,
    UIDesign,
)


class AgentLogEntry(BaseModel):
    timestamp: str
    agent: str
    message: str


class ProjectState(BaseModel):
    project_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    user_prompt: str = ""
    requirements: Optional[Requirements] = None
    design: Optional[UIDesign] = None
    architecture: Optional[Architecture] = None
    content: Optional[Content] = None
    files: GeneratedFiles = Field(default_factory=GeneratedFiles)
    test_results: Optional[TestResults] = None
    quality_report: Optional[QualityReport] = None
    errors: list[str] = Field(default_factory=list)
    agent_logs: list[AgentLogEntry] = Field(default_factory=list)
    iteration: int = 0
    status: ProjectStatus = ProjectStatus.IDLE
    modification_history: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    provider_name: str = ""
    model_name: str = ""

    def elapsed_seconds(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.finished_at if self.finished_at is not None else datetime.now().timestamp()
        return max(0.0, end - self.started_at)

    def log(self, agent: str, message: str) -> None:
        self.agent_logs.append(
            AgentLogEntry(timestamp=datetime.now().strftime("%H:%M:%S"), agent=agent, message=message)
        )

    def get_file(self, path: str):
        for f in self.files.files:
            if f.path == path:
                return f
        return None

    def upsert_files(self, new_files) -> None:
        """Replace files that share a path with `new_files`, append the rest."""
        existing = {f.path: f for f in self.files.files}
        for nf in new_files:
            existing[nf.path] = nf
        self.files.files = list(existing.values())
