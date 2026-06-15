# JARVIS v3.0 — Data-Driven Asynchronous AI Assistant

A complete architectural evolution from v2.0. JARVIS is no longer a terminal chatbot — it is now a **background AI secretary** with a REST API, a real-time WebSocket feed, and a data-driven automation engine. Everything is configurable from a database, not from Python code.

---

## What Changed from v2.0

| v2.0 | v3.0 |
|---|---|
| Synchronous terminal chatbot | Asynchronous backend API + web frontend |
| One user, one conversation | Multi-user, persistent task queue |
| Hard-coded routines in Python | Database-driven routines with cron triggers |
| TTS + Rich console output | Markdown → HTML rendering, served via REST |
| CLI only | FastAPI backend + React PWA (frontend TBD) |
| No scheduling | APScheduler: fire jobs at 6 AM, never write cron |
| Context lost after session | SQLite persists everything: feed, tasks, journal |

### What Was Kept (and Why It Was Good)
- **`OllamaProvider`** — native tool-calling SDK integration, zero changes needed
- **`BaseSkill` + `ToolRegistry`** — auto-discovery drop-in pattern is perfect
- **`IntelligentMemoryManager`** — turn-based summarisation still the right approach
- **`AgentLoop`** — core agentic loop logic reused, stripped of CLI dependencies

### New Capabilities
- **Parallel tool calls** — Gemma4 often calls multiple tools in one response; the new `AgentLoop` handles a list of `ToolCall` objects per chunk natively
- **Markdown rendering** — LLM output is converted to HTML (via `python-markdown` + `pymdownx`) before being stored; the frontend receives clean, ready-to-display HTML
- **Event callbacks** in `AgentLoop` — the worker pushes real-time `tool_call`/`tool_result` events to WebSocket clients while the LLM is still running
- **Per-routine skill gating** — each routine declares which skills it's allowed to use (`allowed_skill_names` JSON), preventing the journal analyser from having access to the smart-home tools

---

## Architecture

```
3dot0/
├── run.py                        # Entry point: starts uvicorn
├── config.yaml                   # All runtime configuration
├── requirements.txt
│
├── app/
│   ├── main.py                   # FastAPI app, lifespan, CORS, router mounts
│   ├── config.py                 # YAML config loader (cached singleton)
│   ├── database.py               # SQLModel engine + session factory
│   ├── models.py                 # All DB tables + API request/response schemas
│   │
│   ├── api/                      # REST API routers (mounted under /api/v1)
│   │   ├── routines.py           # CRUD for automations
│   │   ├── tasks.py              # Job queue: submit, list, cancel
│   │   ├── feed.py               # Activity feed: read, filter, mark-read
│   │   ├── journal.py            # Quick capture journal entries
│   │   ├── skills.py             # Skill registry (read-only)
│   │   ├── users.py              # User management
│   │   └── ws.py                 # WebSocket endpoint (/ws)
│   │
│   ├── core/                     # Provider-agnostic engine
│   │   ├── llm_provider.py       # BaseLLM, StreamChunk, ToolCall
│   │   ├── memory_manager.py     # Turn-based context window + summarisation
│   │   ├── tool_registry.py      # Auto-discovery + per-routine filtering
│   │   ├── agent_loop.py         # Agentic loop (parallel tools, event callbacks)
│   │   └── markdown_utils.py     # Markdown → HTML renderer
│   │
│   ├── providers/
│   │   └── ollama_provider.py    # Ollama SDK adapter
│   │
│   ├── skills/                   # Drop-in skill directory
│   │   ├── base_skill.py
│   │   ├── calculator.py
│   │   ├── system_time.py
│   │   └── memory_skills.py      # save_memory + search_memory (SQLite FTS5)
│   │
│   └── worker/
│       ├── background_worker.py  # Job queue processor thread
│       ├── scheduler.py          # APScheduler: cron routine triggers
│       └── connection_manager.py # WebSocket broadcast (thread-safe)
│
└── tests/
    ├── conftest.py               # In-memory DB, test client, shared fixtures
    ├── test_models.py            # DB model tests
    ├── test_skills.py            # Skill execution tests (no LLM)
    ├── test_agent.py             # AgentLoop tests with mock LLM
    └── test_api.py               # FastAPI endpoint tests
```

---

## How It All Fits Together

### The Data-Driven Core

Routines are rows in the `routines` table, not Python functions. A routine has:
- A **cron expression** (`0 6 * * *` = 6 AM daily)
- A **system prompt** (what persona/task JARVIS should use)
- An **allowed skills list** (which tools this routine can call)

APScheduler reads this table on startup and registers the cron triggers automatically. When a trigger fires, it does not run inference directly — it inserts a row into the `tasks` table and returns immediately.

### The Async Task Queue

```
APScheduler fires
    └→ creates Task(status=queued)

BackgroundWorker polls every 2s
    └→ finds queued Task
    └→ marks status=running → notifies WebSocket
    └→ runs AgentLoop(prompt, allowed_skills)
        └→ LLM streams response
        └→ tool_call events → WebSocket → frontend shows spinner
        └→ parallel tool execution (all tools in one LLM call run together)
        └→ final Markdown response
    └→ renders Markdown → HTML
    └→ creates FeedItem
    └→ marks status=done → notifies WebSocket
```

### WebSocket Events

Connect to `ws://<host>:8000/ws` to receive real-time push notifications:

| Event | When |
|---|---|
| `task_queued` | A new task was added to the queue |
| `task_started` | Worker picked up the task |
| `task_done` | Task finished, feed item available |
| `task_failed` | Task failed (includes error) |
| `feed_new` | New feed item created |
| `tool_call` | LLM is calling a tool (real-time) |
| `tool_result` | Tool returned a result |
| `content_chunk` | Streaming content from the LLM |

### The Feed / Inbox

Every completed task produces a `FeedItem` with:
- `content_markdown` — raw LLM output
- `content_html` — pre-rendered HTML (ready for the frontend `innerHTML`)
- `type` — `briefing` / `report` / `reflection` / `question` / `action`
- `is_read` — flag for the notification badge

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally with a tool-calling model:
  - `gemma4:e4b` ← recommended (strong parallel tool calling)
  - `qwen2.5:7b` ← reliable fallback

```bash
ollama pull gemma4:e4b
```

---

## Installation

```bash
# From the repo root
cd 3dot0

python -m venv .venv
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\Activate.ps1     # Windows PowerShell

pip install -r requirements.txt
```

---

## Running

```bash
# From inside the 3dot0/ directory:
python run.py
```

The API will be available at `http://localhost:8000`.  
Interactive API docs (Swagger UI): `http://localhost:8000/docs`  
ReDoc: `http://localhost:8000/redoc`

---

## Configuration

Edit `config.yaml`:

```yaml
llm:
  model: gemma4:e4b          # Must be pulled in Ollama
  ollama_url: http://localhost:11434
  options:
    num_ctx: 32768
    temperature: 0.7

database:
  path: jarvis.db            # Relative to 3dot0/ directory

worker:
  poll_interval_seconds: 2
  max_tool_iterations: 6

memory:
  max_recent_turns: 8
  max_tokens: 8000

default_user:
  name: "Your Name"
  is_primary: true
```

---

## API Reference

### Key Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/api/v1/feed/` | Get activity feed (paginated) |
| `POST` | `/api/v1/feed/{id}/read` | Mark feed item as read |
| `POST` | `/api/v1/feed/read-all` | Mark all items read |
| `POST` | `/api/v1/tasks/` | Submit a delegation task |
| `GET` | `/api/v1/tasks/` | List tasks (filter by status) |
| `DELETE` | `/api/v1/tasks/{id}` | Cancel a queued task |
| `GET` | `/api/v1/routines/` | List all routines |
| `POST` | `/api/v1/routines/` | Create a routine |
| `PATCH` | `/api/v1/routines/{id}` | Update a routine |
| `DELETE` | `/api/v1/routines/{id}` | Delete a routine |
| `POST` | `/api/v1/journal/` | Quick capture journal entry |
| `GET` | `/api/v1/skills/` | List discovered skills |
| `WS` | `/ws` | Real-time event stream |

Full interactive docs at `/docs` when running.

---

## Adding a New Skill

Drop a `.py` file in `3dot0/app/skills/`. Inherit from `BaseSkill`, define a Pydantic `input_model`, implement `execute()`. The registry picks it up on next boot and syncs it to the `skills` table automatically.

```python
from pydantic import BaseModel, Field
from app.skills.base_skill import BaseSkill

class WeatherInput(BaseModel):
    city: str = Field(description="The city to get weather for.")

class WeatherSkill(BaseSkill):
    name = "get_weather"
    description = "Returns the current weather for a city."
    input_model = WeatherInput

    def execute(self, params: WeatherInput) -> str:
        # your implementation here
        return f"Weather for {params.city}: sunny, 22°C"
```

To restrict a routine to only use this skill, set `allowed_skill_names = '["get_weather"]'` on that routine row.

---

## Running Tests

Tests use an **in-memory SQLite database** and a **mock LLM** — Ollama does not need to be running.

```bash
# From inside the 3dot0/ directory
pytest tests/ -v
```

---

## Network Access (Tailscale / PWA)

For remote access and PWA installation on mobile:

1. Install Tailscale on the Mini PC and your devices.
2. The Mini PC gets a stable hostname like `jarvis.tailnet-name.ts.net`.
3. Point `config.yaml` `server.host` to `0.0.0.0`.
4. Access the API at `https://jarvis.tailnet-name.ts.net:8000`.

For HTTPS locally (required for PWA Service Workers on iOS), use Tailscale's built-in HTTPS certificates (free) or put nginx in front with a self-signed cert.

---

## Database

The SQLite database (`jarvis.db`) is created automatically in the `3dot0/` directory on first boot. It is safe to back up and is already in `.gitignore`.

A separate `jarvis_memory.db` holds long-term factual memories saved by the `save_memory` skill — also auto-created, also in `.gitignore`.
