import yaml
import sys
from providers.ollama_provider import OllamaProvider
from core.tool_registry import ToolRegistry
from core.prompt_manager import build_system_prompt
from core.agent_loop import run_agent_turn


def load_config() -> dict:
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found.")
        sys.exit(1)


def main():
    print("Initializing JARVIS...")
    config = load_config()

    registry = ToolRegistry()
    registry.discover_skills()
    print(f"Loaded {len(registry.tools)} skill(s): {list(registry.tools.keys())}\n")

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider")

    if provider == "ollama":
        llm = OllamaProvider(
            base_url=llm_config.get("ollama_url", "http://localhost:11434/api/chat"),
            model=llm_config.get("model", "llama3.2"),
        )
    else:
        print(f"Unsupported provider: {provider}")
        sys.exit(1)

    print(f"Provider: {provider} | Model: {llm_config.get('model')}")
    print("Type 'exit' to quit.\n")

    messages = [{"role": "system", "content": build_system_prompt(registry.get_all_schemas())}]

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("Shutting down JARVIS...")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        run_agent_turn(messages, llm, registry)


if __name__ == "__main__":
    main()