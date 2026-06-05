import yaml
import sys
import json
import re
from providers.ollama_provider import OllamaProvider
from core.tool_registry import ToolRegistry

def load_config():
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found. Please ensure it is in the root directory.")
        sys.exit(1)

def extract_tool_call(text: str) -> dict | None:
    """Helper to find plain text tool calls inside the LLM's text output."""
    lines = text.strip().split('\n')
    tool_name = None
    args = {}
    
    for line in lines:
        line = line.strip()
        # Look for the exact TOOL trigger phrase
        if line.startswith("TOOL:"):
            tool_name = line.replace("TOOL:", "").strip()
        # If we already found a tool, treat following lines as arguments if they have a colon
        elif tool_name and ":" in line:
            parts = line.split(":", 1)
            args[parts[0].strip()] = parts[1].strip()
            
    if tool_name:
        return {"tool": tool_name, "args": args}
        
    return None

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

    # Get the schemas for all discovered tools
    tool_schemas = registry.get_all_schemas()
    
    # Build a powerful system prompt injected with the tool schemas
    system_prompt = f"""You are JARVIS, a highly efficient local AI assistant.
You have access to the following tools:
{json.dumps(tool_schemas, indent=2)}

RULES FOR TOOLS:
If you can answer the user's question normally, just talk to them.
If you need to perform an action or get data, you MUST use the plain text format below.

Example without arguments:
TOOL: get_system_time

Example with arguments:
TOOL: turn_off_lights
room: living_room

Do not add any conversational text before or after if you are calling a tool.
"""

    messages = [
        {"role": "system", "content": system_prompt}
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

        # --- NEW: TOOL INTERCEPTOR ---
        tool_call = extract_tool_call(response_text)
        
        # If we found valid XML and it has a "tool" key
        if tool_call and "tool" in tool_call:
            tool_name = tool_call["tool"]
            args = tool_call.get("args", {})
            
            print(f"\n[JARVIS is executing tool: {tool_name}]")
            
            # Check if the tool actually exists in our registry
            if tool_name in registry.tools:
                tool_class = registry.tools[tool_name]
                tool_instance = tool_class() # Instantiate the skill
                
                try:
                    # Pass the LLM's arguments into Pydantic for validation
                    validated_args = tool_instance.input_model(**args)
                    
                    # Execute the Python code!
                    result = tool_instance.execute(validated_args)
                    print(f"[Tool Result: {result}]\n")
                except Exception as e:
                    result = f"Error executing tool: {e}"
                    print(f"[Tool Error: {result}]\n")
                
                # Feed the result back to the LLM as a system message
                messages.append({"role": "system", "content": f"Tool '{tool_name}' returned: {result}\nNow respond to the user based on this result."})
                
                # Trigger a second LLM generation to formulate the final answer
                print("JARVIS: ", end="", flush=True)
                final_response = ""
                for chunk in llm.generate(messages):
                    print(chunk, end="", flush=True)
                    final_response += chunk
                print()
                
                # Save the final response to history
                messages.append({"role": "assistant", "content": final_response})
            else:
                print(f"\n[Error: LLM tried to call a non-existent tool: {tool_name}]")

if __name__ == "__main__":
    main()