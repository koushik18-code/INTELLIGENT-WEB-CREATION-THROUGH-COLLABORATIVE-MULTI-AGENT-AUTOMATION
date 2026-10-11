"""
AI Website Builder — backend API.

Run with:  python -m uvicorn backend.main:app --reload

Architecture:

    React frontend  --HTTP/SSE-->  FastAPI (this app)
                                        |
                                        v
                                backend/api/routes.py
                                        |
                                        v
                          backend/services/project_service.py
                                        |
                                        v
                              core/app_service.py  (unchanged)
                                        |
                                        v
                          agents/orchestrator.py -> Agents -> LLM Provider

Nothing about the existing AI pipeline changed to build this file — it is a
thin HTTP wrapper around the same core.app_service functions the previous
Gradio UI called directly.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router

app = FastAPI(title="AI Website Builder API", version="1.0.0")

# The Vite dev server runs on a different origin during local development.
# In production the frontend is typically served separately (or built and
# served as static files by this same process — see README), so this list
# stays narrow and explicit rather than a wildcard.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"name": "AI Website Builder API", "docs": "/docs"}
