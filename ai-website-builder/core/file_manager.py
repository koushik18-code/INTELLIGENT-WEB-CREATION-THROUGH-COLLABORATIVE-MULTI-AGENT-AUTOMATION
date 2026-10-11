"""
Handles everything to do with the generated website living on disk:
writing files into an isolated per-project directory, listing them for the
file explorer UI, reading individual file contents, and zipping the whole
project for download.

Every path is sanitized through core.security before it ever touches the
filesystem.
"""
from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass

from core.logger import log
from core.models import GeneratedFiles
from core.security import UnsafePathError, safe_join

GENERATED_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")
os.makedirs(GENERATED_ROOT, exist_ok=True)


class FileManagerError(Exception):
    pass


@dataclass
class FileNode:
    name: str
    path: str
    is_dir: bool
    children: list["FileNode"]


def project_dir(project_id: str) -> str:
    # project_id itself is generated server-side (uuid hex), but sanitize anyway.
    clean_id = "".join(c for c in project_id if c.isalnum())
    if not clean_id:
        raise FileManagerError("Invalid project id")
    return os.path.join(GENERATED_ROOT, clean_id)


def write_project_files(project_id: str, files: GeneratedFiles) -> str:
    """Write every GeneratedFile to disk inside an isolated project directory."""
    base_dir = project_dir(project_id)
    os.makedirs(base_dir, exist_ok=True)

    written = 0
    for f in files.files:
        try:
            full_path = safe_join(base_dir, f.path)
        except UnsafePathError as e:
            log(f"SECURITY: rejected unsafe generated path '{f.path}': {e}")
            continue
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(f.content)
        written += 1

    log(f"Wrote {written}/{len(files.files)} files to {base_dir}")
    return base_dir


def list_file_tree(project_id: str) -> FileNode:
    base_dir = project_dir(project_id)
    if not os.path.isdir(base_dir):
        return FileNode(name="(empty)", path="", is_dir=True, children=[])

    def build(dir_path: str, rel: str) -> list[FileNode]:
        nodes: list[FileNode] = []
        try:
            entries = sorted(os.listdir(dir_path))
        except FileNotFoundError:
            return nodes
        for entry in entries:
            full = os.path.join(dir_path, entry)
            rel_path = f"{rel}/{entry}" if rel else entry
            if os.path.isdir(full):
                nodes.append(FileNode(name=entry, path=rel_path, is_dir=True, children=build(full, rel_path)))
            else:
                nodes.append(FileNode(name=entry, path=rel_path, is_dir=False, children=[]))
        return nodes

    return FileNode(name="/", path="", is_dir=True, children=build(base_dir, ""))


def list_file_paths(project_id: str) -> list[str]:
    """Flat, sorted list of relative file paths — convenient for a Dropdown."""
    base_dir = project_dir(project_id)
    if not os.path.isdir(base_dir):
        return []
    paths = []
    for root, _dirs, filenames in os.walk(base_dir):
        for fname in filenames:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, base_dir).replace(os.sep, "/")
            paths.append(rel)
    return sorted(paths)


def read_file(project_id: str, relative_path: str) -> str:
    base_dir = project_dir(project_id)
    full_path = safe_join(base_dir, relative_path)
    if not os.path.isfile(full_path):
        raise FileManagerError(f"File not found: {relative_path}")
    with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def get_index_html_path(project_id: str) -> str | None:
    base_dir = project_dir(project_id)
    candidate = os.path.join(base_dir, "index.html")
    return candidate if os.path.isfile(candidate) else None


def build_zip(project_id: str) -> str:
    base_dir = project_dir(project_id)
    if not os.path.isdir(base_dir):
        raise FileManagerError("Nothing has been generated yet for this project")

    zip_path = os.path.join(GENERATED_ROOT, f"{project_id}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, filenames in os.walk(base_dir):
            for fname in filenames:
                full = os.path.join(root, fname)
                arcname = os.path.join("website", os.path.relpath(full, base_dir))
                zf.write(full, arcname)

    log(f"Built ZIP archive at {zip_path}")
    return zip_path


def cleanup_project(project_id: str) -> None:
    base_dir = project_dir(project_id)
    if os.path.isdir(base_dir):
        shutil.rmtree(base_dir)
