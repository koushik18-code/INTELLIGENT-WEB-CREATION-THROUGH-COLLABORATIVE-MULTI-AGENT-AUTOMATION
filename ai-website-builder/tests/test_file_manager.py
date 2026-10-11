import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import zipfile

import pytest

from core import file_manager
from core.models import GeneratedFile, GeneratedFiles


@pytest.fixture
def sample_files():
    return GeneratedFiles(
        files=[
            GeneratedFile(path="index.html", content="<html><body>Hi</body></html>"),
            GeneratedFile(path="css/style.css", content="body{color:red;}"),
            GeneratedFile(path="js/script.js", content="console.log('hi');"),
        ]
    )


def test_write_and_read_roundtrip(sample_files):
    project_id = "testproj01"
    try:
        file_manager.write_project_files(project_id, sample_files)
        assert file_manager.read_file(project_id, "index.html") == sample_files.files[0].content
        assert file_manager.read_file(project_id, "css/style.css") == sample_files.files[1].content
        paths = file_manager.list_file_paths(project_id)
        assert "index.html" in paths
        assert "css/style.css" in paths
        assert "js/script.js" in paths
    finally:
        file_manager.cleanup_project(project_id)


def test_malicious_path_is_skipped_not_written():
    project_id = "testproj02"
    malicious = GeneratedFiles(files=[GeneratedFile(path="assets/ok.png", content="fake")])
    # Directly bypass pydantic validation to simulate a hostile raw dict making it
    # past a hypothetical relaxed schema — file_manager must still refuse it.
    malicious.files.append(GeneratedFile.model_construct(path="../escape.txt", content="bad"))
    try:
        base_dir = file_manager.write_project_files(project_id, malicious)
        escape_path = os.path.join(os.path.dirname(base_dir), "escape.txt")
        assert not os.path.exists(escape_path)
    finally:
        file_manager.cleanup_project(project_id)


def test_build_zip_contains_all_files(sample_files):
    project_id = "testproj03"
    try:
        file_manager.write_project_files(project_id, sample_files)
        zip_path = file_manager.build_zip(project_id)
        assert os.path.isfile(zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert any(n.endswith("index.html") for n in names)
            assert any(n.endswith("style.css") for n in names)
    finally:
        file_manager.cleanup_project(project_id)
        zip_path = os.path.join(file_manager.GENERATED_ROOT, f"{project_id}.zip")
        if os.path.exists(zip_path):
            os.remove(zip_path)


def test_get_index_html_path(sample_files):
    project_id = "testproj04"
    try:
        file_manager.write_project_files(project_id, sample_files)
        assert file_manager.get_index_html_path(project_id) is not None
    finally:
        file_manager.cleanup_project(project_id)


def test_get_index_html_path_missing_project():
    assert file_manager.get_index_html_path("doesnotexist123") is None
