"""
Orchestrator Agent.

The only component allowed to decide execution order, pass data between
agents, and mutate the shared ProjectState. Agents never call each other
directly — everything flows through here, which keeps the workflow
controlled, inspectable, and safe from runaway agent-to-agent loops.

Workflow:

    USER -> REQUIREMENTS -> UI/UX -> ARCHITECTURE -> CONTENT -> CODE GEN
          -> WRITE FILES -> TESTING -> (errors? DEBUG loop, max 5) -> QUALITY
          -> FINAL TEST -> DONE
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from typing import Optional

from agents import (
    architecture_agent,
    change_agent,
    code_agent,
    content_agent,
    debugging_agent,
    quality_agent,
    requirements_agent,
    testing_agent,
    ui_agent,
)
from core.file_manager import write_project_files
from core.llm import LLMError, LLMProvider
from core.logger import log
from core.models import GeneratedFile, ProjectStatus
from core.state import ProjectState

MAX_DEBUG_ITERATIONS = 5

# A progress callback receives (agent_key, status) so the UI can render a
# live checklist. status is one of: "running", "done", "failed".
ProgressCallback = Optional[Callable[[str, str], None]]

PIPELINE_STEPS = [
    ("requirements", "Requirements Agent"),
    ("ui_ux", "UI/UX Agent"),
    ("architecture", "Architecture Agent"),
    ("content", "Content Agent"),
    ("code_gen", "Code Generator"),
    ("testing", "Testing Agent"),
    ("debugging", "Debugging Agent"),
    ("quality", "Quality Agent"),
]


class OrchestratorError(Exception):
    pass


class GenerationCancelled(Exception):
    """Raised internally to unwind the pipeline when the user requests a stop."""


class Orchestrator:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    # ------------------------------------------------------------------ #
    # Full generation pipeline
    # ------------------------------------------------------------------ #
    def run(
        self,
        user_prompt: str,
        on_progress: ProgressCallback = None,
        cancel_event: Optional[threading.Event] = None,
        project_id: Optional[str] = None,
    ) -> ProjectState:
        # When a caller (e.g. the HTTP API) already owns a project id — for
        # instance because it created a URL/session around it before
        # generation started — pin the new state to that id so the files
        # this pipeline writes to disk land in the directory the caller
        # expects. Left unset, ProjectState generates its own id, which is
        # exactly what the previous Gradio UI relied on.
        state = ProjectState(user_prompt=user_prompt, status=ProjectStatus.RUNNING)
        if project_id:
            state.project_id = project_id
        state.started_at = time.time()
        state.provider_name = getattr(self.provider, "name", "")
        state.model_name = getattr(self.provider, "model", "")

        def notify(step: str, status: str) -> None:
            if on_progress:
                on_progress(step, status)

        def check_cancelled() -> None:
            # Cancellation is only ever honored *between* pipeline steps, never
            # in the middle of an in-flight LLM call — that call is left to
            # finish naturally so no half-written state or orphaned request
            # is left behind. This is the "safely possible" stop point.
            if cancel_event is not None and cancel_event.is_set():
                raise GenerationCancelled()

        try:
            check_cancelled()
            notify("requirements", "running")
            state.log("Orchestrator", "Pipeline started")
            log("Orchestrator started")
            state.requirements = requirements_agent.run(self.provider, user_prompt)
            state.log("Requirements Agent", "Requirements generated")
            log("Requirements generated")
            notify("requirements", "done")

            check_cancelled()
            notify("ui_ux", "running")
            state.design = ui_agent.run(self.provider, user_prompt, state.requirements)
            state.log("UI/UX Agent", "UI/UX specification generated")
            log("UI/UX specification generated")
            notify("ui_ux", "done")

            check_cancelled()
            notify("architecture", "running")
            state.architecture = architecture_agent.run(self.provider, state.requirements, state.design)
            state.log("Architecture Agent", "Architecture plan generated")
            log("Architecture plan generated")
            notify("architecture", "done")

            check_cancelled()
            notify("content", "running")
            state.content = content_agent.run(self.provider, user_prompt, state.requirements, state.design)
            state.log("Content Agent", "Content generated")
            log("Content generated")
            notify("content", "done")

            check_cancelled()
            notify("code_gen", "running")
            state.files = code_agent.run(self.provider, state.requirements, state.design, state.architecture, state.content)
            state.log("Code Generator", f"Generated {len(state.files.files)} files")
            log(f"Generated {len(state.files.files)} files")
            notify("code_gen", "done")

            write_project_files(state.project_id, state.files)
            state.log("Orchestrator", "Files written to disk")
            log("Files written to disk")

            check_cancelled()
            notify("testing", "running")
            state.test_results = testing_agent.run(self.provider, state.files)
            state.log(
                "Testing Agent",
                f"{'PASSED' if state.test_results.passed else 'FAILED'} "
                f"({len(state.test_results.errors)} error(s), {len(state.test_results.warnings)} warning(s))",
            )
            log(f"Testing result: passed={state.test_results.passed}")
            notify("testing", "done" if state.test_results.passed else "failed")

            if not state.test_results.passed:
                notify("debugging", "running")
                self._debug_loop(state, cancel_event=cancel_event)
                notify(
                    "debugging",
                    "done" if state.test_results and state.test_results.passed else "failed",
                )
            else:
                notify("debugging", "done")

            check_cancelled()
            notify("quality", "running")
            state.quality_report = quality_agent.run(self.provider, state.requirements, state.design, state.files)
            state.log(
                "Quality Agent",
                f"Score {state.quality_report.score}/100 — {'PASSED' if state.quality_report.passed else 'NEEDS WORK'}",
            )
            log(f"Quality score: {state.quality_report.score}")
            notify("quality", "done")

            write_project_files(state.project_id, state.files)

            if state.test_results and state.test_results.passed and state.quality_report.passed:
                state.status = ProjectStatus.SUCCESS
            elif state.test_results and not state.test_results.passed:
                state.status = ProjectStatus.SUCCESS_WITH_WARNINGS
            else:
                state.status = ProjectStatus.SUCCESS_WITH_WARNINGS

            state.log("Orchestrator", f"Pipeline finished with status: {state.status.value}")
            log(f"Pipeline finished with status: {state.status.value}")
            state.finished_at = time.time()
            return state

        except GenerationCancelled:
            state.status = ProjectStatus.CANCELLED
            state.log("Orchestrator", "Generation cancelled by user")
            log("Generation cancelled by user")
            state.finished_at = time.time()
            return state
        except LLMError as e:
            state.status = ProjectStatus.FAILED
            state.errors.append(str(e))
            state.log("Orchestrator", f"LLM error: {e}")
            log(f"LLM error: {e}")
            state.finished_at = time.time()
            return state
        except Exception as e:  # noqa: BLE001 - top-level safety net, one agent must not crash the app
            state.status = ProjectStatus.FAILED
            state.errors.append(f"Unexpected error: {e}")
            state.log("Orchestrator", f"Unexpected error: {e}")
            log(f"Unexpected error: {e}")
            state.finished_at = time.time()
            return state

    def _debug_loop(self, state: ProjectState, cancel_event: Optional[threading.Event] = None) -> None:
        """Bounded self-correction loop. Never allowed to spin forever."""
        state.iteration = 0
        while state.test_results and not state.test_results.passed and state.iteration < MAX_DEBUG_ITERATIONS:
            if cancel_event is not None and cancel_event.is_set():
                state.log("Debugging Agent", "Cancelled by user before next debug iteration")
                raise GenerationCancelled()
            state.iteration += 1
            state.log(
                "Debugging Agent",
                f"Iteration {state.iteration}/{MAX_DEBUG_ITERATIONS}: attempting to fix "
                f"{len(state.test_results.errors)} error(s)",
            )
            log(f"Debug iteration {state.iteration}: {len(state.test_results.errors)} error(s)")
            try:
                debug_result = debugging_agent.run(self.provider, state.files, state.test_results)
            except LLMError as e:
                state.log("Debugging Agent", f"Debug call failed: {e}")
                log(f"Debug call failed: {e}")
                break

            if not debug_result.files:
                state.log("Debugging Agent", "No fixes proposed — stopping debug loop")
                log("No fixes proposed by debugging agent — stopping")
                break

            state.upsert_files(debug_result.files)
            state.log("Debugging Agent", debug_result.explanation or "Applied fixes")
            write_project_files(state.project_id, state.files)

            state.test_results = testing_agent.run(self.provider, state.files)
            state.log(
                "Testing Agent",
                f"Re-test after iteration {state.iteration}: "
                f"{'PASSED' if state.test_results.passed else f'{len(state.test_results.errors)} error(s) remain'}",
            )
            log(f"Re-test iteration {state.iteration}: passed={state.test_results.passed}")

        if state.test_results and not state.test_results.passed:
            state.log(
                "Orchestrator",
                f"Reached max debug iterations ({MAX_DEBUG_ITERATIONS}) with "
                f"{len(state.test_results.errors)} error(s) remaining — showing current state to user",
            )
            log(f"Max debug iterations reached with {len(state.test_results.errors)} error(s) remaining")

    # ------------------------------------------------------------------ #
    # Modification workflow (continue working on an existing project)
    # ------------------------------------------------------------------ #
    def modify(
        self,
        state: ProjectState,
        modification_request: str,
        on_progress: ProgressCallback = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> ProjectState:
        def notify(step: str, status: str) -> None:
            if on_progress:
                on_progress(step, status)

        def check_cancelled() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise GenerationCancelled()

        try:
            state.status = ProjectStatus.RUNNING
            state.started_at = time.time()
            state.finished_at = None
            state.provider_name = getattr(self.provider, "name", "")
            state.model_name = getattr(self.provider, "model", "")
            state.log("Orchestrator", f"Modification requested: {modification_request}")
            log("Modification workflow started")

            check_cancelled()
            notify("plan", "running")
            plan = change_agent.plan_change(self.provider, state.files, modification_request)
            state.log("Change Planner", f"Affected files: {', '.join(plan.affected_files)} — {plan.plan_summary}")
            log(f"Change plan: {plan.affected_files}")
            notify("plan", "done")

            check_cancelled()
            notify("modify", "running")
            updated = change_agent.apply_change(self.provider, state.files, plan.affected_files, modification_request)
            state.upsert_files(updated.files)
            state.modification_history.append(modification_request)
            state.log("Code Modification Agent", f"Updated {len(updated.files)} file(s)")
            log(f"Modification applied to {[f.path for f in updated.files]}")
            notify("modify", "done")

            write_project_files(state.project_id, state.files)

            check_cancelled()
            notify("testing", "running")
            state.test_results = testing_agent.run(self.provider, state.files)
            notify("testing", "done" if state.test_results.passed else "failed")

            if not state.test_results.passed:
                notify("debugging", "running")
                self._debug_loop(state, cancel_event=cancel_event)
                notify("debugging", "done" if state.test_results.passed else "failed")

            write_project_files(state.project_id, state.files)
            state.status = ProjectStatus.SUCCESS if state.test_results.passed else ProjectStatus.SUCCESS_WITH_WARNINGS
            state.log("Orchestrator", f"Modification finished with status: {state.status.value}")
            log(f"Modification finished: {state.status.value}")
            state.finished_at = time.time()
            return state

        except GenerationCancelled:
            state.status = ProjectStatus.CANCELLED
            state.log("Orchestrator", "Modification cancelled by user")
            log("Modification cancelled by user")
            state.finished_at = time.time()
            return state
        except LLMError as e:
            state.status = ProjectStatus.FAILED
            state.errors.append(str(e))
            state.log("Orchestrator", f"LLM error during modification: {e}")
            log(f"LLM error during modification: {e}")
            state.finished_at = time.time()
            return state
        except Exception as e:  # noqa: BLE001
            state.status = ProjectStatus.FAILED
            state.errors.append(f"Unexpected error during modification: {e}")
            state.log("Orchestrator", f"Unexpected error during modification: {e}")
            log(f"Unexpected error during modification: {e}")
            state.finished_at = time.time()
            return state
