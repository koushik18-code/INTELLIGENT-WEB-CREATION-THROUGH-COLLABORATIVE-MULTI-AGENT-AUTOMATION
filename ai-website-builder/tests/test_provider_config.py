"""Tests for LLM provider/model selection, error handling, and cancellation —
functionality added on top of the original provider abstraction."""
import sys
import threading
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from agents.orchestrator import Orchestrator
from core import app_service
from core.llm import (
    GeminiProvider,
    LLMConfigError,
    MockProvider,
    get_provider,
    model_choices_for,
)
from core.models import ProjectStatus


def test_get_provider_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    provider = get_provider()
    assert isinstance(provider, MockProvider)


def test_get_provider_unknown_name_raises():
    with pytest.raises(LLMConfigError):
        get_provider("not-a-real-provider")


def test_anthropic_provider_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMConfigError):
        get_provider("anthropic")


def test_openai_provider_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMConfigError):
        get_provider("openai")


@pytest.mark.parametrize("provider, env_name", [
    ("groq", "GROQ_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
])
def test_compatible_provider_missing_api_key_raises(monkeypatch, provider, env_name):
    monkeypatch.delenv(env_name, raising=False)
    with pytest.raises(LLMConfigError):
        get_provider(provider)


def test_gemini_provider_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMConfigError):
        get_provider("gemini")


def test_gemini_example_placeholder_is_not_accepted(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    with pytest.raises(LLMConfigError):
        get_provider("gemini")


def test_model_choices_for_mock():
    assert model_choices_for("mock") == ["mock-offline"]


def test_model_choices_for_anthropic_uses_env_default(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-custom-model")
    choices = model_choices_for("anthropic")
    assert choices[0] == "claude-custom-model"
    assert len(choices) == len(set(choices))  # no duplicates


def test_model_choices_for_gemini_uses_env_default(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-model")
    choices = model_choices_for("gemini")
    assert choices[0] == "gemini-custom-model"
    assert len(choices) == len(set(choices))


def test_model_choices_for_gemini_migrates_retired_default(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    choices = model_choices_for("gemini")
    assert choices[0] == "gemini-3.6-flash"


def test_model_choices_for_groq_and_openrouter_defaults():
    assert model_choices_for("groq")[0] == "llama-3.3-70b-versatile"
    assert model_choices_for("openrouter")[0] == "openai/gpt-4o-mini"


class _FakeThinkingConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeGenerateContentConfig:
    last_kwargs = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeGenerateContentConfig.last_kwargs = kwargs


class _FakeTypes:
    ThinkingConfig = _FakeThinkingConfig
    GenerateContentConfig = _FakeGenerateContentConfig


class _ResponseWithTextPropertyError:
    candidates = [
        SimpleNamespace(
            finish_reason="STOP",
            content=SimpleNamespace(parts=[SimpleNamespace(text='{"ok": true}')]),
        )
    ]

    @property
    def text(self):
        raise ValueError("response contains no direct text")


class _FakeModels:
    def __init__(self, response, fail_with_thinking=False):
        self.response = response
        self.kwargs = None
        self.fail_with_thinking = fail_with_thinking
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        if self.fail_with_thinking and "thinking_config" in kwargs["config"].kwargs:
            raise ValueError("thinking_config is not supported by this model")
        return self.response


def _provider_for_fake_client(model, response, fail_with_thinking=False):
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = model
    provider.default_temperature = None
    provider._genai_types = _FakeTypes
    provider._client = SimpleNamespace(
        models=_FakeModels(response, fail_with_thinking=fail_with_thinking)
    )
    return provider


def test_gemini_does_not_send_2_5_thinking_config_to_other_model_families():
    provider = _provider_for_fake_client("gemini-2.0-flash", SimpleNamespace(text="ok"))

    assert provider.complete("system", "user") == "ok"
    assert "thinking_config" not in _FakeGenerateContentConfig.last_kwargs


def test_gemini_2_5_keeps_thinking_config_for_supported_models():
    provider = _provider_for_fake_client("gemini-2.5-flash", SimpleNamespace(text="ok"))

    assert provider.complete("system", "user") == "ok"
    assert _FakeGenerateContentConfig.last_kwargs["thinking_config"].kwargs == {
        "thinking_budget": 0
    }


def test_gemini_3_6_uses_thinking_level():
    provider = _provider_for_fake_client("gemini-3.6-flash", SimpleNamespace(text="ok"))

    assert provider.complete("system", "user") == "ok"
    assert _FakeGenerateContentConfig.last_kwargs["thinking_config"].kwargs == {
        "thinking_level": "low"
    }


def test_gemini_falls_back_to_candidate_parts_when_text_property_fails():
    provider = _provider_for_fake_client("gemini-2.0-flash", _ResponseWithTextPropertyError())

    assert provider.complete("system", "user") == '{"ok": true}'


def test_gemini_retries_without_thinking_config_when_model_rejects_it():
    provider = _provider_for_fake_client(
        "gemini-2.5-flash", SimpleNamespace(text="ok"), fail_with_thinking=True
    )

    assert provider.complete("system", "user") == "ok"
    assert provider._client.models.calls == 2


def test_mock_provider_accepts_model_and_temperature():
    provider = get_provider("mock", model="whatever", temperature=0.3)
    assert provider.model == "whatever"
    assert provider.default_temperature == 0.3
    # Mock still answers deterministically regardless of these settings.
    out = provider.complete("You are the Requirements Agent.", "hello")
    assert out


def test_app_service_caches_provider_per_settings():
    p1 = app_service.get_configured_provider("mock", model="a", temperature=0.1)
    p2 = app_service.get_configured_provider("mock", model="a", temperature=0.1)
    p3 = app_service.get_configured_provider("mock", model="b", temperature=0.1)
    assert p1 is p2  # identical settings reuse the cached instance
    assert p1 is not p3  # different model -> different instance


def test_generation_can_be_cancelled_between_steps():
    """Cancellation is honored between pipeline steps, not mid-call, but it
    must reliably stop the pipeline and mark the project as cancelled."""
    orchestrator = Orchestrator(MockProvider())
    cancel_event = threading.Event()
    seen_steps = []

    def progress_cb(step, status):
        seen_steps.append((step, status))
        if step == "requirements" and status == "done":
            cancel_event.set()

    try:
        state = orchestrator.run(
            "A cancelled project", on_progress=progress_cb, cancel_event=cancel_event
        )
        assert state.status == ProjectStatus.CANCELLED
        # Only the requirements step should have completed before the stop.
        assert ("ui_ux", "running") not in seen_steps
        assert state.finished_at is not None
    finally:
        from core.file_manager import cleanup_project

        cleanup_project(state.project_id)


def test_uncancelled_generation_completes_normally():
    orchestrator = Orchestrator(MockProvider())
    cancel_event = threading.Event()  # never set
    state = orchestrator.run("A normal project", cancel_event=cancel_event)
    try:
        assert state.status in (ProjectStatus.SUCCESS, ProjectStatus.SUCCESS_WITH_WARNINGS)
    finally:
        from core.file_manager import cleanup_project

        cleanup_project(state.project_id)


def test_state_tracks_elapsed_time_and_provider_info():
    orchestrator = Orchestrator(MockProvider())
    state = orchestrator.run("A timed project")
    try:
        assert state.started_at is not None
        assert state.finished_at is not None
        assert state.elapsed_seconds() is not None
        assert state.elapsed_seconds() >= 0
        assert state.provider_name == "mock"
    finally:
        from core.file_manager import cleanup_project

        cleanup_project(state.project_id)
