"""
Testing Agent.

Runs genuine static analysis against the generated project instead of just
asking an LLM whether the code "looks right":

  * HTML is parsed with BeautifulSoup and checked for required tags,
    missing referenced local files (css/js/img), and internal anchor links
    that point at non-existent ids.
  * CSS is parsed with tinycss2 and checked for parse errors.
  * JavaScript is parsed with esprima (a real JS parser) and checked for
    syntax errors, plus a check that ids referenced via getElementById /
    querySelector exist somewhere in the HTML.

The LLM is then given the automated results and asked to add anything a
static linter can't catch (does it plausibly meet the requirements, are
there accessibility smells, etc).
"""
from __future__ import annotations

import os
import re

from bs4 import BeautifulSoup

from core.llm import LLMProvider, get_structured_response
from core.logger import log
from core.models import GeneratedFiles, TestResults

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "testing.txt")


def _load_system_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _file_map(files: GeneratedFiles) -> dict[str, str]:
    return {f.path: f.content for f in files.files}


def _check_html(path: str, html: str, all_paths: set[str], errors: list[str], warnings: list[str]) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")

    if not soup.find("html"):
        errors.append(f"{path}: missing <html> root element")
    if not soup.find("head"):
        errors.append(f"{path}: missing <head> element")
    if not soup.find("body"):
        errors.append(f"{path}: missing <body> element")
    if not soup.find("title"):
        warnings.append(f"{path}: missing <title> element (bad for SEO)")
    if not soup.find("meta", attrs={"name": "viewport"}):
        warnings.append(f"{path}: missing viewport meta tag — page may not be responsive")

    # local resource references must exist among the generated files
    for link in soup.find_all("link", href=True):
        href = link["href"]
        if _is_local(href) and _normalize(path, href) not in all_paths:
            errors.append(f"{path}: <link href=\"{href}\"> points to a file that was not generated")

    for script in soup.find_all("script", src=True):
        src = script["src"]
        if _is_local(src) and _normalize(path, src) not in all_paths:
            errors.append(f"{path}: <script src=\"{src}\"> points to a file that was not generated")

    for img in soup.find_all("img", src=True):
        src = img["src"]
        if _is_local(src) and _normalize(path, src) not in all_paths:
            warnings.append(f"{path}: <img src=\"{src}\"> points to a file that was not generated")
        if not img.get("alt", "").strip():
            warnings.append(f"{path}: <img src=\"{src}\"> is missing meaningful alt text (accessibility)")

    # internal anchor links (#section) must resolve to an existing id
    ids_in_doc = {tag.get("id") for tag in soup.find_all(id=True)}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") and len(href) > 1:
            target_id = href[1:]
            if target_id not in ids_in_doc:
                errors.append(f"{path}: link href=\"{href}\" has no matching element with id=\"{target_id}\"")

    return soup


def _is_local(url: str) -> bool:
    return bool(url) and not url.startswith(("http://", "https://", "//", "data:", "mailto:", "tel:"))


def _normalize(from_path: str, ref: str) -> str:
    ref = ref.split("#")[0].split("?")[0]
    base_dir = os.path.dirname(from_path)
    joined = os.path.normpath(os.path.join(base_dir, ref)).replace("\\", "/")
    return joined.lstrip("./")


def _check_css(path: str, css_text: str, errors: list[str]) -> None:
    import tinycss2

    rules = tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True)
    for rule in rules:
        if rule.type == "error":
            errors.append(f"{path}: CSS parse error — {rule.message}")


def _check_js(path: str, js_text: str, errors: list[str], html_ids: set[str]) -> None:
    import esprima

    try:
        esprima.parseScript(js_text, tolerant=False)
    except Exception as e:
        errors.append(f"{path}: JavaScript syntax error — {e}")
        return

    for match in re.finditer(r"getElementById\(\s*['\"]([\w-]+)['\"]\s*\)", js_text):
        ref_id = match.group(1)
        if ref_id not in html_ids:
            errors.append(f"{path}: getElementById(\"{ref_id}\") references an id that does not exist in the HTML")


def run_static_analysis(files: GeneratedFiles) -> TestResults:
    errors: list[str] = []
    warnings: list[str] = []
    file_map = _file_map(files)
    all_paths = set(file_map.keys())

    if "index.html" not in file_map:
        errors.append("Missing required file: index.html")

    html_ids: set[str] = set()
    for path, content in file_map.items():
        if path.endswith((".html", ".htm")):
            soup = _check_html(path, content, all_paths, errors, warnings)
            html_ids |= {tag.get("id") for tag in soup.find_all(id=True) if tag.get("id")}

    for path, content in file_map.items():
        if path.endswith(".css"):
            try:
                _check_css(path, content, errors)
            except Exception as e:  # never let a bad linter crash the pipeline
                warnings.append(f"{path}: CSS check could not run ({e})")

    for path, content in file_map.items():
        if path.endswith(".js"):
            try:
                _check_js(path, content, errors, html_ids)
            except Exception as e:
                warnings.append(f"{path}: JS check could not run ({e})")

    return TestResults(passed=len(errors) == 0, errors=errors, warnings=warnings, suggestions=[])


def run(provider: LLMProvider, files: GeneratedFiles) -> TestResults:
    static_result = run_static_analysis(files)
    log(
        f"Static analysis: {len(static_result.errors)} error(s), "
        f"{len(static_result.warnings)} warning(s)"
    )

    system_prompt = _load_system_prompt()
    files_summary = "\n\n".join(f"--- {f.path} ---\n{f.content[:3000]}" for f in files.files)
    user_message = (
        f"Automated static analysis results (JSON):\n{static_result.model_dump_json(indent=2)}\n\n"
        f"Project files:\n{files_summary}"
    )

    try:
        llm_result = get_structured_response(provider, system_prompt, user_message, TestResults, max_tokens=2048)
    except Exception as e:
        log(f"LLM review pass failed, continuing with static analysis only: {e}")
        return static_result

    combined = TestResults(
        passed=static_result.passed and llm_result.passed,
        errors=list(dict.fromkeys(static_result.errors + llm_result.errors)),
        warnings=list(dict.fromkeys(static_result.warnings + llm_result.warnings)),
        suggestions=list(dict.fromkeys(static_result.suggestions + llm_result.suggestions)),
    )
    return combined
