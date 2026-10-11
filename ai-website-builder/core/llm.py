"""
LLM provider abstraction.

    LLMProvider
        ├── AnthropicProvider
        ├── OpenAIProvider
        ├── GeminiProvider
        ├── GroqProvider
        ├── OpenRouterProvider
        └── MockProvider

Swapping providers is a one-line change (`LLM_PROVIDER=anthropic|openai|gemini|groq|openrouter|mock`
in `.env`). Every agent talks only to this module, never to a vendor SDK
directly, so a new provider can be added without touching agent code.
"""
from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from core.logger import log

T = TypeVar("T", bound=BaseModel)

_RETIRED_GEMINI_MODELS = {
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
}


class LLMError(Exception):
    """Raised for any provider-level failure (auth, timeout, rate limit, etc.)."""


class LLMConfigError(LLMError):
    """Raised when the provider is missing required configuration (e.g. API key)."""


# --------------------------------------------------------------------------- #
# Abstract base
# --------------------------------------------------------------------------- #
class LLMProvider(ABC):
    name: str = "base"
    model: str = ""
    # Default sampling temperature for this provider instance. Individual
    # calls may override it via the `temperature` kwarg on `complete()`;
    # when they don't (which is how every existing agent calls it), this
    # value is used instead. This lets the UI's temperature slider affect
    # generation without every agent needing to be rewired.
    default_temperature: Optional[float] = None

    def _resolve_temperature(self, temperature: Optional[float]) -> Optional[float]:
        return temperature if temperature is not None else self.default_temperature

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: Optional[float] = None,
    ) -> str:
        """Return the raw text completion for a single-turn prompt."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #
class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMConfigError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file "
                "(see .env.example) or choose a different LLM_PROVIDER."
            )
        try:
            import anthropic
        except ImportError as e:
            raise LLMConfigError("The 'anthropic' package is not installed. Run: pip install anthropic") from e

        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        self.default_temperature = temperature

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: Optional[float] = None,
    ) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        resolved_temp = self._resolve_temperature(temperature)
        if resolved_temp is not None:
            kwargs["temperature"] = resolved_temp
        try:
            response = self._client.messages.create(**kwargs)
        except Exception as e:  # covers auth, rate limit, timeout, connection errors
            raise LLMError(f"Anthropic API call failed: {e}") from e

        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        if not text_parts:
            raise LLMError("Anthropic response contained no text content")
        return "".join(text_parts)


# --------------------------------------------------------------------------- #
# OpenAI-compatible providers (OpenAI, Groq, OpenRouter)
# --------------------------------------------------------------------------- #
class OpenAICompatibleProvider(LLMProvider):
    api_key_env = "OPENAI_API_KEY"
    base_url: Optional[str] = None
    default_model = "gpt-4o"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        api_key = (api_key or os.environ.get(self.api_key_env) or "").strip()
        if not api_key:
            raise LLMConfigError(
                f"{self.api_key_env} is not set. Add it to your .env file "
                "(see .env.example) or choose a different LLM_PROVIDER."
            )
        try:
            import openai
        except ImportError as e:
            raise LLMConfigError("The 'openai' package is not installed. Run: pip install openai") from e

        client_kwargs = {"api_key": api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self._client = openai.OpenAI(**client_kwargs)
        self.model = model or os.environ.get(self.model_env, self.default_model)
        self.default_temperature = temperature

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: Optional[float] = None,
    ) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        resolved_temp = self._resolve_temperature(temperature)
        if resolved_temp is not None:
            kwargs["temperature"] = resolved_temp
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            raise LLMError(f"OpenAI API call failed: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise LLMError(f"{self.name.title()} response contained no text content")
        return content


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    model_env = "OPENAI_MODEL"


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    api_key_env = "GROQ_API_KEY"
    model_env = "GROQ_MODEL"
    base_url = "https://api.groq.com/openai/v1"
    default_model = "llama-3.3-70b-versatile"


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"
    api_key_env = "OPENROUTER_API_KEY"
    model_env = "OPENROUTER_MODEL"
    base_url = "https://openrouter.ai/api/v1"
    default_model = "openai/gpt-4o-mini"


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #
class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        api_key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
        if not api_key or api_key.lower() == "your_gemini_api_key_here":
            raise LLMConfigError(
                "GEMINI_API_KEY is not set. Add it to your .env file "
                "(see .env.example) or choose a different LLM_PROVIDER."
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise LLMConfigError("The 'google-genai' package is not installed. Run: pip install google-genai") from e

        self._genai_types = types
        self._client = genai.Client(api_key=api_key)
        configured_model = model or os.environ.get("GEMINI_MODEL")
        if configured_model in _RETIRED_GEMINI_MODELS:
            configured_model = "gemini-3.6-flash"
        self.model = configured_model or "gemini-3.6-flash"
        self.default_temperature = temperature

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: Optional[float] = None,
    ) -> str:
        config_kwargs = {
            "system_instruction": system_prompt,
            "max_output_tokens": max_tokens,
        }
        resolved_temp = self._resolve_temperature(temperature)
        if resolved_temp is not None:
            config_kwargs["temperature"] = resolved_temp

        # Gemini 2.5 uses a token budget, while Gemini 3.x uses a thinking
        # level. Keep the model-specific setting narrow because sending the
        # wrong variant makes otherwise valid requests fail with a 400.
        model_name = self.model.lower()
        if model_name.startswith("gemini-2.5-"):
            thinking_budget = 128 if "pro" in model_name else 0
            config_kwargs["thinking_config"] = self._genai_types.ThinkingConfig(
                thinking_budget=thinking_budget
            )
        elif model_name.startswith("gemini-3"):
            config_kwargs["thinking_config"] = self._genai_types.ThinkingConfig(
                thinking_level="low"
            )

        try:
            config = self._genai_types.GenerateContentConfig(**config_kwargs)
            response = self._client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=config,
            )
        except Exception as first_error:
            # Older google-genai versions and some model aliases reject the
            # optional thinking field even though the rest of the request is
            # valid. Retry once with the portable GenerateContentConfig shape
            # before reporting a real API/auth/model failure.
            if "thinking_config" not in config_kwargs:
                raise LLMError(f"Gemini API call failed: {first_error}") from first_error
            try:
                fallback_kwargs = {
                    key: value for key, value in config_kwargs.items()
                    if key != "thinking_config"
                }
                fallback_config = self._genai_types.GenerateContentConfig(**fallback_kwargs)
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=fallback_config,
                )
            except Exception as fallback_error:
                raise LLMError(
                    "Gemini API call failed with thinking configuration and with "
                    f"the compatibility retry: {fallback_error}"
                ) from fallback_error

        # The SDK's convenience `response.text` property can itself raise when
        # the response contains no text (for example a safety block). Read it
        # defensively, then inspect candidate parts to produce a useful error
        # instead of leaking an SDK exception from the background worker.
        try:
            content = getattr(response, "text", None)
        except Exception:
            content = None
        if not content:
            try:
                parts = response.candidates[0].content.parts
                content = "".join(
                    part.text for part in parts if getattr(part, "text", None)
                )
            except (AttributeError, IndexError, TypeError):
                content = None
        if not content:
            finish_reason = None
            try:
                finish_reason = response.candidates[0].finish_reason
            except (AttributeError, IndexError, TypeError):
                pass
            if finish_reason is not None and "MAX_TOKENS" in str(finish_reason):
                raise LLMError(
                    "Gemini response contained no text content (ran out of "
                    f"output tokens before answering — finish_reason={finish_reason}, "
                    f"max_output_tokens={max_tokens}). Try increasing max_tokens for this request."
                )
            raise LLMError(
                f"Gemini response contained no text content (finish_reason={finish_reason})"
            )
        return content


# --------------------------------------------------------------------------- #
# Mock provider (for tests / offline development)
# --------------------------------------------------------------------------- #
class MockProvider(LLMProvider):
    """
    Deterministic offline provider. It does not call any network API — it
    inspects the prompt to figure out which agent is calling it and returns
    a valid, schema-shaped JSON response. This lets the entire pipeline and
    test suite run without any API credits.
    """

    name = "mock"
    model = "mock-offline"

    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None):
        # Accepted for interface symmetry with the real providers; the mock
        # provider is deterministic and ignores model/temperature entirely.
        self.model = model or "mock-offline"
        self.default_temperature = temperature

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: Optional[float] = None,
    ) -> str:
        # Dispatch on the SYSTEM prompt only. Each agent's system prompt names
        # itself ("You are the X Agent") and that text never appears inside
        # the user_prompt payloads the agents pass each other, so this avoids
        # accidentally matching on data that merely *mentions* another
        # agent's output (e.g. the Content agent's user message embeds the
        # phrase "Requirements specification").
        sp = system_prompt.lower()

        if "requirements agent" in sp:
            return json.dumps(_MOCK_REQUIREMENTS)
        if "ui/ux agent" in sp:
            return json.dumps(_MOCK_DESIGN)
        if "architecture agent" in sp:
            return json.dumps(_MOCK_ARCHITECTURE)
        if "content agent" in sp:
            return json.dumps(_MOCK_CONTENT)
        if "code generation agent" in sp:
            return json.dumps(_MOCK_FILES)
        if "quality agent" in sp:
            return json.dumps({"score": 88, "passed": True, "issues": [], "recommendations": ["Add a favicon."]})
        if "debugging agent" in sp:
            return json.dumps({"files": [], "explanation": "No changes needed (mock provider)."})
        if "testing agent" in sp:
            return json.dumps({"passed": True, "errors": [], "warnings": [], "suggestions": []})
        if "change planner" in sp:
            return json.dumps({"affected_files": ["css/style.css"], "plan_summary": "Update styling (mock)."})
        if "code modification agent" in sp:
            return json.dumps(self._mock_modification(user_prompt))

        return json.dumps({"note": "mock response", "prompt_seen": user_prompt[:80]})

    @staticmethod
    def _mock_modification(user_prompt: str) -> dict:
        """Return the same files that were sent in, unchanged, so the
        modification workflow has something valid to work with offline."""
        files = []
        for match in re.finditer(r"--- (.+?) ---\n(.*?)(?=\n--- |\Z)", user_prompt, re.DOTALL):
            path, content = match.group(1).strip(), match.group(2).strip()
            files.append({"path": path, "content": content})
        return {"files": files}


_MOCK_REQUIREMENTS = {
    "website_type": "portfolio",
    "target_audience": "recruiters and clients",
    "purpose": "Showcase a software developer's skills and projects",
    "sections": ["hero", "about", "skills", "projects", "testimonials", "contact"],
    "features": ["contact form", "smooth scrolling", "responsive layout"],
    "style": {"theme": "dark", "tone": "professional"},
    "color_palette": {"primary": "#3B82F6", "secondary": "#8B5CF6", "accent": "#F59E0B",
                       "background": "#0F172A", "text": "#F8FAFC"},
    "typography": {"heading_font": "Poppins, sans-serif", "body_font": "Inter, sans-serif", "base_size": "16px"},
    "animations": ["fade-in on scroll", "hover transitions"],
    "responsive_requirements": ["mobile", "tablet", "desktop"],
    "functional_requirements": ["working contact form validation", "sticky nav"],
    "content_requirements": ["realistic project descriptions", "bio text"],
}

_MOCK_DESIGN = {
    "layout": "Single-page scrolling layout with sticky top navigation",
    "navigation": "Fixed top navbar with anchor links to each section",
    "sections": ["hero", "about", "skills", "projects", "testimonials", "contact"],
    "component_hierarchy": [
        {"name": "Navbar", "description": "Logo + links + mobile hamburger menu"},
        {"name": "Hero", "description": "Headline, subheadline, CTA button"},
        {"name": "ProjectCard", "description": "Reusable card for project section"},
    ],
    "color_system": {"primary": "#3B82F6", "secondary": "#8B5CF6", "background": "#0F172A"},
    "typography": {"heading_font": "Poppins", "body_font": "Inter"},
    "spacing_system": "8px base unit scale",
    "buttons_style": "Rounded, gradient fill, subtle hover lift",
    "cards_style": "Glassmorphism with soft shadow",
    "animations": ["fade-in on scroll", "hover lift on cards"],
    "responsive_behavior": "Stacks to single column below 768px, hamburger nav below 900px",
    "mobile_design_notes": "Large tap targets, collapsible nav",
    "accessibility_notes": ["Sufficient color contrast", "Keyboard-navigable nav", "aria-labels on icons"],
}

_MOCK_ARCHITECTURE = {
    "technologies": ["HTML5", "CSS3", "Vanilla JavaScript"],
    "files": [
        {"path": "index.html", "purpose": "Main page markup"},
        {"path": "css/style.css", "purpose": "All styling"},
        {"path": "js/script.js", "purpose": "Interactivity: nav toggle, scroll animations, form validation"},
        {"path": "README.md", "purpose": "Instructions for the generated site"},
    ],
    "css_organization": "single stylesheet using CSS custom properties for theme tokens",
    "js_modules": ["navigation", "scrollAnimations", "formValidation"],
    "assets_needed": [],
    "dependencies": [],
}

_MOCK_CONTENT = {
    "site_title": "Alex Rivera — Software Developer",
    "tagline": "Building fast, accessible, delightful web experiences.",
    "sections": [
        {"section": "hero", "heading": "Hi, I'm Alex Rivera", "subheading": "Full-Stack Software Developer",
         "body": "I design and build performant web applications end to end.",
         "cta_text": "View My Work", "items": []},
        {"section": "about", "heading": "About Me", "subheading": "",
         "body": "Five years building products used by thousands of people.",
         "cta_text": "", "items": []},
        {"section": "skills", "heading": "Skills", "subheading": "", "body": "",
         "cta_text": "", "items": [{"name": "JavaScript"}, {"name": "Python"}, {"name": "React"}]},
        {"section": "projects", "heading": "Projects", "subheading": "", "body": "",
         "cta_text": "", "items": [{"name": "Analytics Dashboard", "description": "Real-time metrics UI"}]},
        {"section": "testimonials", "heading": "What People Say", "subheading": "", "body": "",
         "cta_text": "", "items": [{"quote": "Alex is an outstanding engineer.", "author": "Jamie Lee"}]},
        {"section": "contact", "heading": "Get In Touch", "subheading": "",
         "body": "Have a project in mind? Let's talk.", "cta_text": "Send Message", "items": []},
    ],
}

_MOCK_FILES = {
    "files": [
        {
            "path": "index.html",
            "content": (
                "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
                "<meta charset=\"UTF-8\">\n"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
                "<title>Alex Rivera — Software Developer</title>\n"
                "<link rel=\"stylesheet\" href=\"css/style.css\">\n"
                "</head>\n<body>\n"
                "<nav class=\"navbar\"><div class=\"logo\">Alex</div>"
                "<ul class=\"nav-links\"><li><a href=\"#hero\">Home</a></li>"
                "<li><a href=\"#about\">About</a></li><li><a href=\"#projects\">Projects</a></li>"
                "<li><a href=\"#contact\">Contact</a></li></ul></nav>\n"
                "<section id=\"hero\" class=\"section hero\"><h1>Hi, I'm Alex Rivera</h1>"
                "<p>Full-Stack Software Developer</p><a class=\"btn\" href=\"#projects\">View My Work</a></section>\n"
                "<section id=\"about\" class=\"section\"><h2>About Me</h2>"
                "<p>Five years building products used by thousands of people.</p></section>\n"
                "<section id=\"projects\" class=\"section\"><h2>Projects</h2>"
                "<div class=\"card\"><h3>Analytics Dashboard</h3><p>Real-time metrics UI</p></div></section>\n"
                "<section id=\"contact\" class=\"section\"><h2>Get In Touch</h2>"
                "<form id=\"contact-form\"><input type=\"text\" name=\"name\" placeholder=\"Name\" required>"
                "<input type=\"email\" name=\"email\" placeholder=\"Email\" required>"
                "<textarea name=\"message\" placeholder=\"Message\" required></textarea>"
                "<button type=\"submit\" class=\"btn\">Send Message</button></form></section>\n"
                "<script src=\"js/script.js\"></script>\n</body>\n</html>"
            ),
        },
        {
            "path": "css/style.css",
            "content": (
                ":root{--primary:#3B82F6;--secondary:#8B5CF6;--bg:#0F172A;--text:#F8FAFC;}\n"
                "*{box-sizing:border-box;margin:0;padding:0;}\n"
                "body{font-family:Inter,sans-serif;background:var(--bg);color:var(--text);}\n"
                ".navbar{position:fixed;top:0;width:100%;display:flex;justify-content:space-between;"
                "padding:1rem 2rem;background:rgba(15,23,42,0.8);backdrop-filter:blur(8px);z-index:10;}\n"
                ".nav-links{display:flex;list-style:none;gap:1.5rem;}\n"
                ".nav-links a{color:var(--text);text-decoration:none;}\n"
                ".section{padding:6rem 2rem;max-width:1100px;margin:0 auto;}\n"
                ".hero{text-align:center;padding-top:10rem;}\n"
                ".btn{display:inline-block;padding:0.75rem 1.5rem;border-radius:999px;"
                "background:linear-gradient(90deg,var(--primary),var(--secondary));"
                "color:#fff;text-decoration:none;border:none;cursor:pointer;transition:transform .2s;}\n"
                ".btn:hover{transform:translateY(-2px);}\n"
                ".card{background:rgba(255,255,255,0.05);border-radius:12px;padding:1.5rem;"
                "backdrop-filter:blur(6px);}\n"
                "form{display:flex;flex-direction:column;gap:1rem;max-width:480px;}\n"
                "input,textarea{padding:0.75rem;border-radius:8px;border:1px solid #334155;"
                "background:#1e293b;color:var(--text);}\n"
                "@media (max-width:768px){.nav-links{display:none;}}\n"
            ),
        },
        {
            "path": "js/script.js",
            "content": (
                "document.addEventListener('DOMContentLoaded', function () {\n"
                "  var form = document.getElementById('contact-form');\n"
                "  if (form) {\n"
                "    form.addEventListener('submit', function (e) {\n"
                "      e.preventDefault();\n"
                "      alert('Thanks! This is a demo form.');\n"
                "    });\n"
                "  }\n"
                "  var links = document.querySelectorAll('a[href^=\"#\"]');\n"
                "  links.forEach(function (link) {\n"
                "    link.addEventListener('click', function (e) {\n"
                "      var target = document.querySelector(link.getAttribute('href'));\n"
                "      if (target) {\n"
                "        e.preventDefault();\n"
                "        target.scrollIntoView({ behavior: 'smooth' });\n"
                "      }\n"
                "    });\n"
                "  });\n"
                "});\n"
            ),
        },
        {
            "path": "README.md",
            "content": "# Alex Rivera — Portfolio\n\nGenerated static site. Open `index.html` in a browser.\n",
        },
    ]
}


# --------------------------------------------------------------------------- #
# Known model choices per provider (for the UI's Model dropdown). The
# .env-configured ANTHROPIC_MODEL / OPENAI_MODEL value is always injected as
# an extra option so a custom/self-configured model is never hidden.
# --------------------------------------------------------------------------- #
ANTHROPIC_MODEL_CHOICES = [
    "claude-sonnet-4-6",
    "claude-opus-4-1",
    "claude-haiku-4-5",
]
OPENAI_MODEL_CHOICES = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
]
GROQ_MODEL_CHOICES = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
]
OPENROUTER_MODEL_CHOICES = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "meta-llama/llama-3.3-70b-instruct",
]
GEMINI_MODEL_CHOICES = [
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
]
def model_choices_for(provider_name: str) -> list[str]:
    """Model options to show in the UI for a given provider, with the
    provider's configured .env default listed first."""
    provider_name = (provider_name or "").strip().lower()
    if provider_name == "anthropic":
        default = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        choices = [default] + [m for m in ANTHROPIC_MODEL_CHOICES if m != default]
        return choices
    if provider_name == "openai":
        default = os.environ.get("OPENAI_MODEL", "gpt-4o")
        choices = [default] + [m for m in OPENAI_MODEL_CHOICES if m != default]
        return choices
    if provider_name == "groq":
        default = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        choices = [default] + [m for m in GROQ_MODEL_CHOICES if m != default]
        return choices
    if provider_name == "openrouter":
        default = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        choices = [default] + [m for m in OPENROUTER_MODEL_CHOICES if m != default]
        return choices
    if provider_name == "gemini":
        default = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        if default in _RETIRED_GEMINI_MODELS:
            default = "gemini-3.6-flash"
        choices = [default] + [m for m in GEMINI_MODEL_CHOICES if m != default]
        return choices
    return ["mock-offline"]


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def get_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> LLMProvider:
    provider_name = (provider_name or os.environ.get("LLM_PROVIDER", "mock")).strip().lower()
    if provider_name == "anthropic":
        return AnthropicProvider(model=model, temperature=temperature)
    if provider_name == "openai":
        return OpenAIProvider(model=model, temperature=temperature)
    if provider_name == "groq":
        return GroqProvider(model=model, temperature=temperature)
    if provider_name == "openrouter":
        return OpenRouterProvider(model=model, temperature=temperature)
    if provider_name == "gemini":
        return GeminiProvider(model=model, temperature=temperature)
    if provider_name == "mock":
        return MockProvider(model=model, temperature=temperature)
    raise LLMConfigError(f"Unknown LLM_PROVIDER '{provider_name}'. Use anthropic, openai, gemini, or mock.")


# --------------------------------------------------------------------------- #
# JSON extraction + structured output helper (used by every agent)
# --------------------------------------------------------------------------- #
def extract_json(text: str) -> dict:
    """
    Pull a JSON object out of raw LLM text, tolerating markdown code fences
    and leading/trailing prose that some models add despite instructions.
    """
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse JSON from LLM response: {e}\n---\n{text[:500]}")

    raise ValueError(f"No JSON object found in LLM response:\n---\n{text[:500]}")


def get_structured_response(
    provider: LLMProvider,
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    max_tokens: int = 4096,
    max_retries: int = 2,
    temperature: Optional[float] = None,
) -> T:
    """
    Call the provider and validate the response against `schema`. If parsing
    or validation fails, retry with an explicit repair prompt before giving
    up. This is the one place structured-output trust decisions are made.
    """
    last_error: Optional[str] = None
    current_user_prompt = user_prompt

    for attempt in range(1, max_retries + 2):
        try:
            raw = provider.complete(system_prompt, current_user_prompt, max_tokens=max_tokens, temperature=temperature)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Unexpected error calling provider '{provider.name}': {e}") from e

        try:
            data = extract_json(raw)
            return schema.model_validate(data)
        except (ValueError, ValidationError) as e:
            last_error = str(e)
            log(f"Structured output validation failed (attempt {attempt}): {last_error[:200]}")
            current_user_prompt = (
                f"{user_prompt}\n\n"
                "Your previous response could not be parsed as valid JSON matching the required "
                f"schema. The error was:\n{last_error}\n\n"
                "Return ONLY a single valid JSON object. No markdown fences, no commentary, "
                "no trailing text before or after the JSON."
            )
            time.sleep(0.2)

    raise LLMError(
        f"Failed to get a valid structured response from '{provider.name}' after "
        f"{max_retries + 1} attempts. Last error: {last_error}"
    )
