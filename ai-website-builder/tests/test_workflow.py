import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from agents.orchestrator import Orchestrator
from core.file_manager import cleanup_project
from core.llm import MockProvider
from core.models import ProjectStatus


@pytest.fixture
def orchestrator():
    return Orchestrator(MockProvider())


def test_full_pipeline_produces_files(orchestrator):
    state = orchestrator.run("Create a modern portfolio website for a software developer.")
    try:
        assert state.status in (ProjectStatus.SUCCESS, ProjectStatus.SUCCESS_WITH_WARNINGS)
        assert state.requirements is not None
        assert state.design is not None
        assert state.architecture is not None
        assert state.content is not None
        assert len(state.files.files) > 0
        assert any(f.path == "index.html" for f in state.files.files)
        assert state.test_results is not None
        assert state.quality_report is not None
    finally:
        cleanup_project(state.project_id)


def test_pipeline_progress_callback_fires(orchestrator):
    seen = []
    state = orchestrator.run("A bakery landing page", on_progress=lambda step, status: seen.append((step, status)))
    try:
        step_names = {s for s, _ in seen}
        assert "requirements" in step_names
        assert "code_gen" in step_names
        assert "testing" in step_names
    finally:
        cleanup_project(state.project_id)


def test_empty_prompt_raises():
    from core import app_service

    with pytest.raises(ValueError):
        app_service.generate_website("", "mock")


def test_modification_workflow(orchestrator):
    state = orchestrator.run("A portfolio site for a designer")
    try:
        original_css = state.get_file("css/style.css").content
        modified_state = orchestrator.modify(state, "Change the accent color to purple")
        assert modified_state.status in (ProjectStatus.SUCCESS, ProjectStatus.SUCCESS_WITH_WARNINGS)
        assert len(modified_state.modification_history) == 1
        # index.html must still exist and be untouched/valid after a CSS-only change
        assert modified_state.get_file("index.html") is not None
    finally:
        cleanup_project(state.project_id)


def test_debug_loop_has_iteration_cap():
    from agents.orchestrator import MAX_DEBUG_ITERATIONS

    assert MAX_DEBUG_ITERATIONS == 5
