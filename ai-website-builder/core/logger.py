"""
Logging utilities.

Writes to logs/app.log and also keeps an in-memory ring buffer that the
Gradio UI polls to show live agent activity. API keys / secrets are
redacted before anything is written or displayed.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from collections import deque
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_SECRET_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9\-_]{10,})"),
    re.compile(r"(ANTHROPIC_API_KEY\s*=\s*)\S+"),
    re.compile(r"(OPENAI_API_KEY\s*=\s*)\S+"),
]


def _redact(message: str) -> str:
    redacted = message
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: (m.group(1) + "***REDACTED***") if m.groups() else "***REDACTED***", redacted)
    return redacted


class _MemoryHandler(logging.Handler):
    """Keeps the most recent N log lines in memory for the UI."""

    def __init__(self, capacity: int = 500):
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        msg = _redact(self.format(record))
        with self._lock:
            self.buffer.append(msg)

    def get_lines(self) -> list[str]:
        with self._lock:
            return list(self.buffer)

    def clear(self) -> None:
        with self._lock:
            self.buffer.clear()


_formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_formatter)

memory_handler = _MemoryHandler()
memory_handler.setFormatter(_formatter)

logger = logging.getLogger("ai_website_builder")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    logger.addHandler(_file_handler)
    logger.addHandler(memory_handler)


def log(message: str) -> str:
    """Log a redacted message and return the formatted line (useful for tests)."""
    safe = _redact(message)
    logger.info(safe)
    return f"[{datetime.now().strftime('%H:%M:%S')}] {safe}"


def get_recent_logs() -> list[str]:
    return memory_handler.get_lines()


def clear_logs() -> None:
    memory_handler.clear()
