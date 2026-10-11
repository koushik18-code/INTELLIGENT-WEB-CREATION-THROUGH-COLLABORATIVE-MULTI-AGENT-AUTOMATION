import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from pydantic import ValidationError

from core.models import GeneratedFile, GeneratedFiles, Requirements, TestResults


def test_requirements_defaults():
    r = Requirements()
    assert r.website_type == "general"
    assert r.color_palette.primary.startswith("#")
    assert r.responsive_requirements == ["mobile", "tablet", "desktop"]


def test_generated_file_rejects_path_traversal():
    with pytest.raises(ValidationError):
        GeneratedFile(path="../../etc/passwd", content="oops")


def test_generated_file_rejects_absolute_path():
    with pytest.raises(ValidationError):
        GeneratedFile(path="/etc/passwd", content="oops")


def test_generated_file_accepts_normal_path():
    f = GeneratedFile(path="css/style.css", content="body{}")
    assert f.path == "css/style.css"


def test_generated_files_container():
    files = GeneratedFiles(files=[GeneratedFile(path="index.html", content="<html></html>")])
    assert len(files.files) == 1


def test_test_results_defaults_to_failed():
    t = TestResults()
    assert t.passed is False
    assert t.errors == []
