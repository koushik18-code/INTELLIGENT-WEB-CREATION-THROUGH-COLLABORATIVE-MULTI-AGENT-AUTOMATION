# AI Website Builder

Describe a website in plain language and a team of specialized AI agents —
Requirements, UI/UX, Architecture, Content, Code, Testing, Debugging, and
Quality — plans, writes, tests, and refines a real, working HTML/CSS/JS
website for you. Preview it live, ask for changes in plain language, and
export a clean ZIP when you're happy.

This project was migrated from a Gradio UI to a proper client/server
architecture. **Gradio is no longer used anywhere** — the frontend is a
custom React + Vite application, talking to a FastAPI backend over HTTP and
Server-Sent Events.

## Architecture

```
React (Vite) frontend  --HTTP + SSE-->  FastAPI backend
                                              |
                                    backend/api/routes.py
                                              |
                                backend/services/project_service.py
                                              |
                                    core/app_service.py        <- unchanged
                                              |
                          agents/orchestrator.py -> Agents -> LLM Provider
```

The entire AI pipeline (`agents/`, `core/`, `prompts/`) is untouched by this
migration. `backend/` is a thin HTTP wrapper around the same
`core.app_service` functions the old Gradio UI called directly — nothing
about how websites are generated, tested, or debugged changed.

```
ai-website-builder/
├── backend/                 # FastAPI app (new)
│   ├── main.py               # app entrypoint, CORS
│   ├── api/routes.py          # HTTP + SSE endpoints
│   └── services/
│       ├── project_service.py   # in-memory project registry, background jobs
│       └── providers_service.py # read-only provider/model info for the UI
├── frontend/                # React + Vite app (new)
│   └── src/
│       ├── pages/             # Landing, Builder
│       ├── components/        # Nav, AgentPipeline, PreviewPane, FileExplorer
│       ├── animations/        # GSAP ScrollTrigger reveal hook
│       ├── api/client.js      # fetch + SSE wrapper
│       └── styles/            # design tokens, global styles
├── agents/                  # unchanged — the 9 specialized agents + orchestrator
├── core/                    # unchanged — LLM providers, state, security, file manager
├── prompts/                 # unchanged
├── generated/                # generated project output (gitignored)
├── tests/                   # unchanged pytest suite (still passing)
└── README.md
```

## Features

- **Cinematic landing page** — large serif headline, GSAP `ScrollTrigger`
  scroll storytelling (Describe → Understand → Design → Architect → Create
  → Test → Refine → Launch), and a live-cycling agent pipeline visualization.
- **Builder page** — a creative-tool layout (not a dashboard): prompt +
  structured config on the left, live sandboxed preview / file explorer in
  the center, agent activity + project dashboard + refine box on the right.
- **Live generation via Server-Sent Events** — the frontend receives real
  backend state as each agent runs; nothing is faked.
- **Provider/model/temperature selection** — Mock (offline, no API key),
  Anthropic, OpenAI, Google Gemini, Groq, and OpenRouter. API keys never leave
  the server.
- **Device preview modes** — desktop / tablet / mobile, plus fullscreen.
- **File explorer** with a real syntax-highlighted code viewer
  (`highlight.js`), restricted to the generated project's own directory.
- **Refine/modify workflow** — plain-language change requests re-run the
  existing Change Planner → Code Modification → Testing → Debugging
  pipeline and only touch the files that need to change.
- **ZIP export**, safe path validation, and project isolation — all
  preserved from the original security model.

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- (Optional) an Anthropic, OpenAI, Gemini, Groq, or OpenRouter API key — the Mock provider needs neither

## 1. Python setup

```powershell
cd path\to\ai-website-builder
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

(macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`)

## 2. Environment configuration

```powershell
copy .env.example .env
```

Edit `.env`:

```
LLM_PROVIDER=mock
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-6
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
```

- **Mock provider**: leave `LLM_PROVIDER=mock` and leave the API keys blank.
  The full pipeline runs offline, deterministically, at no cost — this is
  what the automated test suite uses.
- **Anthropic**: set `ANTHROPIC_API_KEY`. Provider/model can also be changed
  live from the Builder UI regardless of this default.
- **OpenAI**: set `OPENAI_API_KEY`. Same as above.
- **Gemini**: set `GEMINI_API_KEY`. The default model is `gemini-3.6-flash`.
- **Groq**: set `GROQ_API_KEY`. The default model is `llama-3.3-70b-versatile`.
  Groq is accessed through its OpenAI-compatible API.
- **OpenRouter**: set `OPENROUTER_API_KEY`. The default model is
  `openai/gpt-4o-mini`; OpenRouter model slugs can be changed from the Builder
  UI. OpenRouter is accessed through its OpenAI-compatible API.

If a required key is missing, the backend does not crash — the generation
fails gracefully with a clear message surfaced in the UI's activity panel.

## 3. Frontend installation

```powershell
cd frontend
npm install
```

## 4. Starting the backend

From the project root (with the virtualenv active):

```powershell
python -m uvicorn backend.main:app --reload
```

The API is now at `http://127.0.0.1:8000` (interactive docs at `/docs`).

## 5. Starting the frontend

In a second terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` requests
to the backend, so no CORS configuration is needed in development.

## 6. Running the tests

```powershell
pytest tests/ -v
```

The suite (36 tests) runs entirely offline against the `MockProvider` and
covers: Pydantic model validation, path-traversal/security rejection, file
writing/ZIP export, provider/model/temperature configuration, missing
API-key handling, safe cancellation, and full pipeline + modification runs
through the real `Orchestrator`. These tests exercise `agents/` and `core/`
directly and know nothing about FastAPI or React — the backend/frontend
migration cannot break them, and it hasn't.

## 7. Building the frontend for production

```powershell
cd frontend
npm run build
```

Output goes to `frontend/dist/`. Serve it with any static file host, or
point a reverse proxy at it alongside the FastAPI backend. Update
`CORS_ORIGINS` in `.env` if the frontend is served from a different origin
than the Vite dev default.

## API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/providers` | List providers, their models, and whether each is configured |
| POST | `/api/projects` | Create a new project session, returns `project_id` |
| POST | `/api/projects/{id}/generate` | Start generation (prompt + provider/model/temperature) |
| POST | `/api/projects/{id}/modify` | Start a refine/modification pass |
| POST | `/api/projects/{id}/cancel` | Request a safe stop (honored between agent steps) |
| POST | `/api/projects/{id}/reset` | Delete the project's files and its session |
| GET | `/api/projects/{id}/status` | Snapshot of current status (polling fallback) |
| GET | `/api/projects/{id}/events` | Server-Sent Events stream of live progress |
| GET | `/api/projects/{id}/files` | File tree for the generated project |
| GET | `/api/projects/{id}/files/{path}` | A single file's content + detected language |
| GET | `/api/projects/{id}/preview` | Sanitized preview HTML for the sandboxed iframe |
| GET | `/api/projects/{id}/export` | Download the project as a ZIP |

## Security model (unchanged)

- Generated projects are isolated under `generated/<project_id>/`.
- Path traversal (`../`), absolute paths, null bytes, and disallowed
  extensions are rejected by `core/security.py` before any file read/write.
- The live preview renders inside a sandboxed `<iframe sandbox="allow-scripts">`
  with no same-origin access to the parent app.
- API keys live only in backend environment variables; they are never sent
  to the frontend and are redacted from logs.
- No generated Python, shell, or npm/node commands are ever executed.

## Known limitations

- The in-memory project registry (`backend/services/project_service.py`)
  is single-process: restarting the backend clears active sessions (not
  generated files on disk, which persist under `generated/`). For a
  production deployment with multiple workers, swap this for a shared
  store (e.g. Redis) — the `ProjectSession` interface is small and isolated
  on purpose to make that swap contained.
- SSE streams one active listener per project at a time; a second browser
  tab watching the same project will get the current snapshot on connect
  but not duplicate the live stream. Polling `/status` always works as a
  fallback.
- Google Fonts (`Instrument Serif`, `Inter`) are loaded from
  `fonts.googleapis.com`; a fully offline dev environment will fall back to
  the browser's default serif/sans-serif fonts, which doesn't affect
  functionality.

## Confirmation

Gradio has been fully removed: `app.py` (the old Gradio UI) is deleted,
`gradio`/`gradio_client` are uninstalled and no longer in
`requirements.txt`, and a repository-wide search confirms zero remaining
references to `gradio`, `gr.Blocks`, or `gr.Interface`.
