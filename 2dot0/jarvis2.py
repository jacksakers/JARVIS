#!/usr/bin/env python3
"""
JARVIS v2.0  —  Local AI Assistant
────────────────────────────────────────────────────────────────────────────────
Run from inside the 2dot0/ directory:
    python jarvis2.py

Or from the repo root:
    python 2dot0/jarvis2.py
────────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import threading
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
# Ensure this file's directory is on sys.path so that all local packages
# (core/, providers/, skills/) are importable regardless of where Python
# is launched from.
_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Change CWD so relative paths (config.yaml, memory DB, TTS temp files) work
os.chdir(_HERE)
# ─────────────────────────────────────────────────────────────────────────────

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle

from providers.ollama_provider import OllamaProvider
from core.tool_registry import ToolRegistry
from core.memory_manager import IntelligentMemoryManager
from core.tts_engine import TTSEngine
from core.agent_loop import AgentLoop

# ── Global state ──────────────────────────────────────────────────────────────
console = Console()
stop_event = threading.Event()
# ─────────────────────────────────────────────────────────────────────────────


# ═════════════════════════════════════════════════════════════════════════════
# Config
# ═════════════════════════════════════════════════════════════════════════════

def load_config(path: str = "config.yaml") -> dict:
    try:
        with open(path, "r") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        console.print(f"[red]Error: {path} not found.[/red]")
        sys.exit(1)
    except yaml.YAMLError as exc:
        console.print(f"[red]Config parse error: {exc}[/red]")
        sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════════
# System prompt
# ═════════════════════════════════════════════════════════════════════════════

def build_system_prompt(tool_count: int) -> str:
    return f"""\
You are JARVIS, a highly capable and efficient local AI assistant. \
You are concise, direct, and proactive.

You have access to {tool_count} tool(s). Use them when you need real-time data, \
need to perform an action, or are uncertain of a fact. \
After using a tool, respond naturally based on the result — never just echo the raw output.

When you can answer from general knowledge, do so directly without calling a tool.\
"""


# ═════════════════════════════════════════════════════════════════════════════
# CLI UI helpers
# ═════════════════════════════════════════════════════════════════════════════

def print_banner() -> None:
    console.print(
        Panel(
            Text.from_markup(
                "[bold cyan]J.A.R.V.I.S[/bold cyan]\n"
                "[dim]Just A Rather Very Intelligent System[/dim]\n"
                "[dim]v2.0 — Local AI Assistant[/dim]"
            ),
            expand=False,
            border_style="cyan",
            padding=(1, 4),
        )
    )
    console.print()


def print_help() -> None:
    console.print(
        Panel(
            "[bold]Built-in commands[/bold]\n\n"
            "  [cyan]/help[/cyan]          Show this help message\n"
            "  [cyan]/skills[/cyan]        List all loaded skills\n"
            "  [cyan]/memory[/cyan]        Show current session summary & stats\n"
            "  [cyan]/tts [on|off][/cyan]  Toggle text-to-speech\n"
            "  [cyan]/clear[/cyan]         Clear conversation history\n"
            "  [cyan]/model[/cyan]         Show current model details\n"
            "  [cyan]exit / quit[/cyan]    Shut down JARVIS\n\n"
            "[bold]Keyboard shortcuts[/bold]\n\n"
            "  [cyan]Ctrl+C[/cyan]         Interrupt current response & stop voice\n"
            "  [cyan]↑ / ↓[/cyan]          Navigate input history",
            title="Help",
            border_style="dim",
            expand=False,
        )
    )


def print_skills(registry: ToolRegistry) -> None:
    if not registry.tools:
        console.print("[dim]No skills loaded.[/dim]")
        return
    lines = []
    for name, skill_cls in registry.tools.items():
        lines.append(f"  [cyan]{name}[/cyan]  —  {skill_cls.description}")
    console.print(
        Panel(
            "\n".join(lines),
            title=f"Skills  ({len(registry.tools)} loaded)",
            border_style="dim",
            expand=False,
        )
    )


def print_memory_status(memory: IntelligentMemoryManager) -> None:
    parts = [f"[dim]Completed turns in window:[/dim] {memory.turn_count}"]
    parts.append(f"[dim]Estimated context tokens:[/dim] ~{memory.estimated_tokens:,}")
    if memory.session_summary:
        console.print(
            Panel(
                memory.session_summary,
                title="Session Summary",
                border_style="dim",
                expand=False,
            )
        )
    console.print("\n".join(parts))


def print_model_info(llm_config: dict) -> None:
    console.print(
        Panel(
            f"[dim]Provider:[/dim] {llm_config.get('provider', 'ollama')}\n"
            f"[dim]Model:[/dim]    {llm_config.get('model', 'unknown')}\n"
            f"[dim]URL:[/dim]      {llm_config.get('ollama_url', 'http://localhost:11434')}",
            title="Model",
            border_style="dim",
            expand=False,
        )
    )


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    config = load_config()
    llm_cfg = config.get("llm", {})
    tts_cfg = config.get("tts", {})
    mem_cfg = config.get("memory", {})

    print_banner()

    # ── TTS ──────────────────────────────────────────────────────────────────
    tts = TTSEngine(
        voice=tts_cfg.get("voice", "en-GB-RyanNeural"),
        enabled=tts_cfg.get("enabled", True),
    )

    # ── Skills ───────────────────────────────────────────────────────────────
    console.print("[dim]Scanning for skills...[/dim]")
    registry = ToolRegistry()
    registry.discover_skills()
    skill_names = list(registry.tools.keys())
    console.print(
        f"[dim]Loaded [bold]{len(skill_names)}[/bold] skill(s): "
        f"{', '.join(skill_names) or 'none'}[/dim]\n"
    )

    # ── LLM provider ─────────────────────────────────────────────────────────
    provider_name = llm_cfg.get("provider", "ollama")
    if provider_name != "ollama":
        console.print(f"[red]Unsupported provider: {provider_name}[/red]")
        sys.exit(1)

    llm = OllamaProvider(
        model=llm_cfg.get("model", "llama3.2:3b"),
        base_url=llm_cfg.get("ollama_url", "http://localhost:11434"),
        options=llm_cfg.get("options", {}),
    )

    console.print("[dim]Connecting to Ollama...[/dim]", end="")
    if not llm.test_connection():
        console.print(
            "\n[red]Cannot reach Ollama or model not found. "
            "Is Ollama running and is the model pulled?[/red]"
        )
        sys.exit(1)
    console.print(" [green]OK[/green]\n")

    # ── Memory ───────────────────────────────────────────────────────────────
    tool_schemas = registry.get_all_tool_schemas()
    system_prompt = build_system_prompt(len(tool_schemas))

    memory = IntelligentMemoryManager(
        system_prompt=system_prompt,
        max_recent_turns=mem_cfg.get("max_recent_turns", 6),
        max_tokens=mem_cfg.get("max_tokens", 5000),
    )

    # ── Agent loop ───────────────────────────────────────────────────────────
    agent = AgentLoop(
        llm=llm,
        registry=registry,
        memory=memory,
        tts=tts,
        console=console,
        stop_event=stop_event,
    )

    # ── Greeting ─────────────────────────────────────────────────────────────
    greeting = "Hello sir. JARVIS online. How can I help?"
    console.print(f"[bold cyan]JARVIS:[/bold cyan] {greeting}")
    tts.speak(greeting)
    console.print()

    # ── Input session (with persistent history) ───────────────────────────
    history_path = _HERE / ".jarvis_history"
    session: PromptSession = PromptSession(
        history=FileHistory(str(history_path)),
        style=PTStyle.from_dict({"prompt": "bold white"}),
    )

    console.print(
        "[dim]Type [bold]/help[/bold] for commands · "
        "[bold]Ctrl+C[/bold] to interrupt a response · "
        "[bold]exit[/bold] to quit[/dim]\n"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Main loop
    # ═════════════════════════════════════════════════════════════════════════
    while True:
        # ── Read input ───────────────────────────────────────────────────────
        try:
            user_input = session.prompt("You: ").strip()
        except KeyboardInterrupt:
            # Ctrl+C while typing — silence TTS and let the user re-type
            tts.stop_all()
            console.print("\n[dim](Stopped. Type your message.)[/dim]\n")
            continue
        except EOFError:
            break  # Ctrl+D

        if not user_input:
            continue

        lower = user_input.lower()

        # ── Built-in commands ─────────────────────────────────────────────
        if lower in ("exit", "quit", "/exit", "/quit"):
            farewell = "Goodbye, sir. Shutting down."
            console.print(f"\n[bold cyan]JARVIS:[/bold cyan] {farewell}")
            tts.speak(farewell)
            import time; time.sleep(2)  # let TTS finish the farewell
            break

        if lower in ("/help", "help"):
            print_help()
            continue

        if lower == "/skills":
            print_skills(registry)
            continue

        if lower == "/memory":
            print_memory_status(memory)
            continue

        if lower == "/clear":
            memory.clear()
            console.print("[dim]Conversation history cleared.[/dim]\n")
            continue

        if lower == "/model":
            print_model_info(llm_cfg)
            continue

        if lower.startswith("/tts"):
            parts = lower.split()
            if len(parts) > 1 and parts[1] == "off":
                tts.enabled = False
                console.print("[dim]TTS disabled.[/dim]\n")
            elif len(parts) > 1 and parts[1] == "on":
                tts.enabled = True
                console.print("[dim]TTS enabled.[/dim]\n")
            else:
                state = "enabled" if tts.enabled else "disabled"
                console.print(f"[dim]TTS is currently {state}.[/dim]\n")
            continue

        # ── Run the agent turn ────────────────────────────────────────────
        console.print(Rule(style="dim"))
        stop_event.clear()

        try:
            agent.run_turn(user_input)
        except KeyboardInterrupt:
            stop_event.set()
            tts.stop_all()
            console.print("\n[dim yellow](Response interrupted)[/dim yellow]")
            stop_event.clear()

        console.print()

    # ── Shutdown ──────────────────────────────────────────────────────────────
    tts.shutdown()
    console.print("[dim]JARVIS shutdown complete.[/dim]")


if __name__ == "__main__":
    main()
