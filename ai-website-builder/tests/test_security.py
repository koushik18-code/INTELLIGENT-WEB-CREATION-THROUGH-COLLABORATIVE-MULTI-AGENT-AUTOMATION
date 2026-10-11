import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from core.security import UnsafePathError, safe_join, sanitize_relative_path


def test_sanitize_normal_path():
    assert sanitize_relative_path("css/style.css") == "css/style.css"


def test_sanitize_rejects_parent_traversal():
    with pytest.raises(UnsafePathError):
        sanitize_relative_path("../../etc/passwd")


def test_sanitize_rejects_embedded_traversal():
    with pytest.raises(UnsafePathError):
        sanitize_relative_path("css/../../secret.txt")


def test_sanitize_rejects_absolute_path():
    with pytest.raises(UnsafePathError):
        sanitize_relative_path("/etc/passwd")


def test_sanitize_rejects_windows_drive():
    with pytest.raises(UnsafePathError):
        sanitize_relative_path("C:\\Windows\\System32\\config")


def test_sanitize_rejects_disallowed_extension():
    with pytest.raises(UnsafePathError):
        sanitize_relative_path("run.sh")


def test_sanitize_rejects_null_byte():
    with pytest.raises(UnsafePathError):
        sanitize_relative_path("index.html\x00.js")


def test_safe_join_stays_within_base(tmp_path=None):
    with tempfile.TemporaryDirectory() as base:
        joined = safe_join(base, "js/script.js")
        assert joined.startswith(base)


def test_safe_join_blocks_escape():
    with tempfile.TemporaryDirectory() as base:
        with pytest.raises(UnsafePathError):
            safe_join(base, "../outside.txt")
