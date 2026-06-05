import yaml
import sys
from providers.ollama_provider import OllamaProvider
from core.tool_registry import ToolRegistry

def load_config():
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found. Please ensure it is in the root directory.")
        sys.exit(1)

def main():
    print("Initializing JARVIS Framework...")
    config = load_config()
    
    # Initialize and run the Tool Registry
    print("Scanning for skills...")
    registry = ToolRegistry()
    registry.discover_skills()
    print(f"Discovered {len(registry.tools)} skill(s): {list(registry.tools.keys())}\n")
    
    llm_config = config.get("llm", {})
    provider_name = llm_config.get("provider")
    
    if provider_name == "ollama":
        llm = OllamaProvider(
            base_url=llm_config.get("ollama_url", "http://localhost:11434/api/chat"),
            model=llm_config.get("model", "llama3.2")
        )
    else:
        print(f"Unsupported provider: {provider_name}")
        sys.exit(1)

    print(f"Connected to {provider_name} using model: {llm_config.get('model')}")
    print("Type 'exit' or 'quit' to stop.\n")

    messages = [
        {"role": "system", "content": "You are JARVIS, a highly efficient local AI assistant. Keep responses concise."}
    ]

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']:
            print("Shutting down JARVIS...")
            break
        
        messages.append({"role": "user", "content": user_input})
        
        print("JARVIS: ", end="", flush=True) # Start the line without a newline
        
        response_text = ""
        # Iterate through the generator and print tokens instantly
        for chunk in llm.generate(messages):
            print(chunk, end="", flush=True)
            response_text += chunk
            
        print() # Add a final newline when the stream finishes
        
        # Append the full compiled response to history
        messages.append({"role": "assistant", "content": response_text})

if __name__ == "__main__":
    main()