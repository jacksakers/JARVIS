# JARVIS — Local AI Assistant Framework

A lightweight, modular Python framework for running a fully local, private AI assistant powered by [Ollama](https://ollama.com). Built for 24/7 deployment on low-power hardware (tested on Ryzen 4300U, 16 GB RAM).

## Features

- **Streaming CLI** — token-by-token output, fast feel even on small models
- **Plug-and-play skills** — drop a `.py` file into `skills/` and it's auto-discovered
- **Recursive tool calling** — JARVIS chains tool calls until it has a complete answer
- **Long-term memory** — SQLite + FTS5 full-text search for facts, preferences, and logs
- **LLM-agnostic** — swap providers via `config.yaml`, no code changes needed
- **Enforced reasoning** — system prompt encourages chain-of-thought before every action

## Architecture

```
jarvis.py                  # Thin CLI entry point
config.yaml                # LLM provider + model config
│
├── core/
│   ├── llm_provider.py    # Abstract LLM interface (adapter pattern)
│   ├── tool_registry.py   # Auto-discovers skills from skills/
│   ├── prompt_manager.py  # Builds the system prompt with tool schemas
│   ├── agent_loop.py      # Recursive tool-calling loop
│   └── memory.py          # SQLite + FTS5 memory backend
│
├── providers/
│   └── ollama_provider.py # Streaming Ollama adapter
│
└── skills/
    ├── base_skill.py      # BaseSkill abstract class (all skills inherit this)
    ├── system_time.py     # get_system_time
    ├── memory_search.py   # search_memory
    ├── memory_save.py     # save_memory
    └── memory_dynamic.py  # save_dynamic_record
```

## Quick Start

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Pull a model in Ollama**
```bash
ollama pull llama3.2:3b
```

**3. Configure** — edit `config.yaml`:
```yaml
llm:
  provider: ollama
  ollama_url: http://localhost:11434/api/chat
  model: llama3.2:3b
```

**4. Run**
```bash
python jarvis.py
```

## Memory System

JARVIS persists information to `jarvis_memory.db` (SQLite) via three skills:

| Skill | Purpose | Example |
|---|---|---|
| `save_memory` | Structured facts (entity/attribute/value) | User diet = Keto |
| `save_dynamic_record` | Flexible JSON logs under a category | Shopping list, car maintenance |
| `search_memory` | Full-text keyword search across all stored data | "diet food allergies" |

JARVIS automatically searches memory when it detects it needs stored context.

## Adding a New Skill

1. Create `skills/my_skill.py`
2. Inherit from `BaseSkill`, define a Pydantic `input_model`, implement `execute()`
3. Restart JARVIS — it auto-discovers the new skill

```python
from pydantic import BaseModel
from skills.base_skill import BaseSkill

class MyInput(BaseModel):
    query: str

class MySkill(BaseSkill):
    name = "my_skill"
    description = "Does something useful."
    keywords = ["useful", "thing"]
    input_model = MyInput

    def execute(self, params: MyInput) -> str:
        return f"Result for: {params.query}"
```

## How Tool Calling Works

The LLM uses a plain-text format (reliable on small local models):

```
I need to look this up.
TOOL: search_memory
keywords: diet food preferences
```

JARVIS catches this, executes the tool, feeds the result back, and the LLM continues — calling more tools if needed before giving its final answer.

## Roadmap

- [ ] Home automation skills (Kasa/Tapo lights)
- [ ] Web search skill
- [ ] Daily briefing scheduler (APScheduler)
- [ ] FastAPI + web UI frontend
- [ ] Autonomous coding agent (model swap + Smolagents)
- [ ] Tailscale remote access
