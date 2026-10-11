"""
Structured data models shared by every agent.

All inter-agent communication happens through these Pydantic models so that
LLM output is validated before it is trusted anywhere else in the system.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Requirements
# --------------------------------------------------------------------------- #
class ColorPalette(BaseModel):
    primary: str = "#3B82F6"
    secondary: str = "#8B5CF6"
    accent: str = "#F59E0B"
    background: str = "#0F172A"
    text: str = "#F8FAFC"


class Typography(BaseModel):
    heading_font: str = "Poppins, sans-serif"
    body_font: str = "Inter, sans-serif"
    base_size: str = "16px"


class Requirements(BaseModel):
    website_type: str = Field(default="general", description="e.g. portfolio, landing page, blog")
    target_audience: str = "general audience"
    purpose: str = ""
    sections: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    style: dict[str, str] = Field(default_factory=dict)
    color_palette: ColorPalette = Field(default_factory=ColorPalette)
    typography: Typography = Field(default_factory=Typography)
    animations: list[str] = Field(default_factory=list)
    responsive_requirements: list[str] = Field(
        default_factory=lambda: ["mobile", "tablet", "desktop"]
    )
    functional_requirements: list[str] = Field(default_factory=list)
    content_requirements: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# UI / UX design
# --------------------------------------------------------------------------- #
class ComponentSpec(BaseModel):
    name: str
    description: str = ""


class UIDesign(BaseModel):
    layout: str = ""
    navigation: str = ""
    sections: list[str] = Field(default_factory=list)
    component_hierarchy: list[ComponentSpec] = Field(default_factory=list)
    color_system: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, str] = Field(default_factory=dict)
    spacing_system: str = ""
    buttons_style: str = ""
    cards_style: str = ""
    animations: list[str] = Field(default_factory=list)
    responsive_behavior: str = ""
    mobile_design_notes: str = ""
    accessibility_notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Architecture
# --------------------------------------------------------------------------- #
class ArchitectureFile(BaseModel):
    path: str
    purpose: str = ""


class Architecture(BaseModel):
    technologies: list[str] = Field(default_factory=lambda: ["HTML5", "CSS3", "Vanilla JavaScript"])
    files: list[ArchitectureFile] = Field(default_factory=list)
    css_organization: str = "single stylesheet with CSS custom properties"
    js_modules: list[str] = Field(default_factory=list)
    assets_needed: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #
class SectionContent(BaseModel):
    section: str
    heading: str = ""
    subheading: str = ""
    body: str = ""
    cta_text: str = ""
    items: list[dict[str, str]] = Field(default_factory=list)


class Content(BaseModel):
    site_title: str = ""
    tagline: str = ""
    sections: list[SectionContent] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Generated files
# --------------------------------------------------------------------------- #
class GeneratedFile(BaseModel):
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def no_traversal(cls, v: str) -> str:
        if ".." in v or v.startswith("/") or v.startswith("\\"):
            raise ValueError(f"Unsafe path rejected: {v}")
        return v


class GeneratedFiles(BaseModel):
    files: list[GeneratedFile] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Testing
# --------------------------------------------------------------------------- #
class TestResults(BaseModel):
    passed: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #
class QualityReport(BaseModel):
    score: int = 0
    passed: bool = False
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Debugging
# --------------------------------------------------------------------------- #
class DebugResult(BaseModel):
    files: list[GeneratedFile] = Field(default_factory=list)
    explanation: str = ""


class ChangePlan(BaseModel):
    affected_files: list[str] = Field(default_factory=list)
    plan_summary: str = ""


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ProjectStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"
