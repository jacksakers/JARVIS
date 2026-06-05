# JARVIS v2.0

A production-ready local AI assistant powered by Ollama, with native tool calling, intelligent memory management, streaming TTS, and a polished CLI.

---

## What's New in v2.0

### Native Tool Calling (biggest change)
v1 used a fragile text-parsing hack (`TOOL: <name>` in plain text) that confused smaller models. v2 uses the **official Ollama Python SDK** with the proper `tools=` parameter — the same JSON function-calling spec used by OpenAI. The model is given structured tool schemas and returns structured tool call objects. No regex. No hallucinated formats.

### Intelligent Memory Management
v1 kept a flat list of all messages and dropped the oldest one when the token limit was hit. This caused the LLM to see partial context for a question answered 5 turns ago, leading to confusion.

v2 groups messages into **turns** (one turn = the user message + all tool calls + the assistant's final answer that answered it). When the context window fills up:
1. Older turns are fed to the LLM and **summarised into concise bullet points**.
2. The raw tool-call structures are replaced with that readable summary.
3. Only the most recent N turns are kept as live messages.

This means stale tool call payloads from old questions never pollute a new question's context.

### Interruptible Streaming Response
Press **Ctrl+C** during any response to instantly:
- Stop the LLM stream mid-sentence.
- Silence the voice playback.
- Return to the input prompt cleanly.

### Sentence-level Streaming TTS
v1 queued full responses before speaking. v2 detects sentence boundaries in real-time as the LLM streams, so the voice starts speaking the first sentence while the LLM is still generating the rest.

### Rich CLI
- Spinner while the LLM is thinking.
- Colour-coded output (tool calls, results, errors).
- Persistent input history (↑/↓ to navigate previous queries).
- Built-in slash commands (see below).

### New Built-in Skills
| Skill | What it does |
|---|---|
| `get_system_time` | Returns current date and time |
| `calculate` | Safely evaluates maths expressions using AST (no `eval`) |
| `save_memory` | Persists facts to a local SQLite database |
| `search_memory` | Full-text search across saved memories (SQLite FTS5) |

### Proper Provider Abstraction
The `BaseLLM` abstract class now exposes two methods: `generate()` (simple streaming, used for summarisation) and `stream()` (full streaming with tool support). Adding a new provider (e.g. OpenAI) is a matter of implementing those two methods — the agent loop needs zero changes.

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally with at least one model pulled
- A model that supports tool calling is strongly recommended:
  - `qwen2.5:3b` or `qwen2.5:7b` ← best tool-calling performance at small size
  - `llama3.2:3b` ← decent, lighter
  - `mistral:7b` ← good all-rounder

```bash
ollama pull qwen2.5:3b
```

---

## Installation

```bash
# 1. Clone / copy the 2dot0/ folder to your machine

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\Activate.ps1      # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Running

```bash
# From inside the 2dot0/ directory:
python jarvis2.py
```

> The script sets its own working directory automatically, so you can also run it from the repo root with `python 2dot0/jarvis2.py`.

---

## Configuration

Edit `2dot0/config.yaml` before running:

```yaml
llm:
  provider: ollama
  ollama_url: http://localhost:11434   # change if Ollama is on another machine
  model: qwen2.5:3b                   # must be pulled in Ollama
  options:
    num_ctx: 8192                      # context window size
    temperature: 0.7

tts:
  enabled: true
  voice: en-GB-RyanNeural             # any Edge TTS voice

memory:
  max_recent_turns: 6                 # turns to keep as live messages
  max_tokens: 5000                    # soft token budget
```

---

## Built-in Commands

Once running, type any of these at the `You:` prompt:

| Command | Action |
|---|---|
| `/help` | Show command reference |
| `/skills` | List all loaded skills and their descriptions |
| `/memory` | Show session summary and context stats |
| `/tts on` / `/tts off` | Toggle voice on or off at runtime |
| `/clear` | Wipe conversation history |
| `/model` | Show current model and provider details |
| `exit` / `quit` | Graceful shutdown |

**Ctrl+C** at any point during a response interrupts the stream and stops the voice.

---

## Adding a New Skill

Drop a `.py` file into `2dot0/skills/`. Inherit from `BaseSkill`, define a Pydantic `input_model`, and implement `execute()`. The registry picks it up automatically on next start — no registration step required.

```python
from pydantic import BaseModel, Field
from skills.base_skill import BaseSkill

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

The Ollama tool schema is generated automatically from the class — no manual JSON needed.

---

## Project Structure

```
2dot0/
├── jarvis2.py              # Main entry point / CLI controller
├── config.yaml             # All runtime configuration
├── requirements.txt
│
├── core/
│   ├── llm_provider.py     # BaseLLM abstract class + StreamChunk / ToolCall types
│   ├── tool_registry.py    # Auto-discovery engine for skills/
│   ├── memory_manager.py   # Turn-based intelligent memory with LLM summarisation
│   ├── tts_engine.py       # Edge-TTS engine with sentence streaming and stop support
│   └── agent_loop.py       # Streaming agentic loop with tool execution
│
├── providers/
│   └── ollama_provider.py  # Ollama SDK adapter implementing BaseLLM
│
└── skills/
    ├── base_skill.py        # BaseSkill ABC with auto schema generation
    ├── system_time.py       # get_system_time
    ├── calculator.py        # calculate (AST-safe expression evaluator)
    └── memory_skills.py     # save_memory + search_memory (SQLite FTS5)
```

---

## Memory Database

Long-term memories are stored in `jarvis_memory.db` (SQLite) created automatically in the `2dot0/` directory on first use. The file is already in `.gitignore`. Back it up to preserve memories across reinstalls.
