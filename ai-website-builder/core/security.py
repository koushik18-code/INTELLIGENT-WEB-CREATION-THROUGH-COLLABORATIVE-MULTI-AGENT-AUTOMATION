"""
Security helpers.

Generated websites are AI-produced and must never be able to read or write
outside of their own isolated project directory. Every path that comes from
an LLM response is treated as untrusted input and passed through
`sanitize_relative_path` before it touches the filesystem.
"""
from __future__ import annotations

import os
import posixpath

MAX_PATH_LENGTH = 260
ALLOWED_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".json", ".md", ".txt",
    ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".webmanifest",
}


class UnsafePathError(ValueError):
    pass


def sanitize_relative_path(raw_path: str) -> str:
    """
    Normalize a relative file path and reject anything that could escape
    the project sandbox: absolute paths, parent-directory traversal ('..'),
    null bytes, drive letters, or disallowed file extensions.
    """
    if not raw_path or not isinstance(raw_path, str):
        raise UnsafePathError("Empty or invalid path")

    if "\x00" in raw_path:
        raise UnsafePathError("Null byte in path")

    if len(raw_path) > MAX_PATH_LENGTH:
        raise UnsafePathError("Path too long")

    normalized = raw_path.replace("\\", "/").strip()

    if normalized.startswith("/") or normalized.startswith("~"):
        raise UnsafePathError(f"Absolute paths are not allowed: {raw_path}")

    if ":" in normalized:  # e.g. C:\ or file://
        raise UnsafePathError(f"Path contains drive/scheme separator: {raw_path}")

    # posixpath.normpath collapses "./" and "a/../b" style segments so we can
    # reliably detect any attempt to climb above the project root.
    collapsed = posixpath.normpath(normalized)

    if collapsed == "." or collapsed.startswith("..") or "/../" in ("/" + collapsed + "/"):
        raise UnsafePathError(f"Path traversal detected: {raw_path}")

    ext = os.path.splitext(collapsed)[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise UnsafePathError(f"File extension not allowed: {ext}")

    return collapsed


def is_within_directory(base_dir: str, target_path: str) -> bool:
    """Confirm that target_path resolves to somewhere inside base_dir."""
    base_dir = os.path.realpath(base_dir)
    target_path = os.path.realpath(target_path)
    return os.path.commonpath([base_dir]) == os.path.commonpath([base_dir, target_path])


def safe_join(base_dir: str, relative_path: str) -> str:
    """Sanitize `relative_path` and join it to `base_dir`, re-verifying containment."""
    clean = sanitize_relative_path(relative_path)
    joined = os.path.join(base_dir, clean)
    if not is_within_directory(base_dir, joined):
        raise UnsafePathError(f"Resolved path escapes sandbox: {relative_path}")
    return joined
