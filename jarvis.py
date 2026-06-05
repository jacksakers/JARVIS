import yaml
import sys
import json
import re
import random

from providers.ollama_provider import OllamaProvider
from core.tool_registry import ToolRegistry
from core.memory_manager import ConversationBuffer
from core.tts_engine import speak, stream_speak

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
        
        # Start capturing when we see TOOL:
        if line.startswith("TOOL:"):
            tool_name = line.replace("TOOL:", "").strip()
            continue
            
        # If we have found a tool, look for arguments
        if tool_name:
            if ":" in line:
                parts = line.split(":", 1)
                args[parts[0].strip()] = parts[1].strip()
            elif line == "":
                # Stop parsing if we hit a blank line after the tool call
                # This prevents accidentally grabbing later conversational text
                continue
            else:
                # If there's non-empty text without a colon, we've moved past the tool block
                break
            
    if tool_name:
        return {"tool": tool_name, "args": args}
        
    return None

def compress_history(messages: list[dict], llm: "BaseLLM") -> str:
    """Helper to compress conversation history using the LLM itself."""
    compress_prompt = """Please compact the conversation history to essential information needed to understand 
                        the current context in plain text. If in doubt, keep it but if it is redundant, 
                        contradictive, or does not add value, remove it."""
    
    compress_messages = [{"role": "user", "content": compress_prompt}]
    
    # Create a plain text version of the conversation history for the LLM to compress. This is more expensive but allows the LLM to decide what to keep.
    compress_history = ""
    for msg in messages:
        if "role" not in msg:
            continue
        if msg["role"] == "system" and "You are JARVIS" in msg["content"]:
            continue
        compress_history += f"{msg['role']}: {msg['content']}\n"
    
    compress_messages.append({"role": "system", "content": compress_history})
    
    compressed_result = ""
    for chunk in llm.generate(compress_messages):
        compressed_result += chunk
        
    return compressed_result

def main():
    print("Initializing JARVIS Framework...")
    stream_speak("Hello sir. How can I help?...")
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
You ONLY have access to the following tools:
{json.dumps(tool_schemas, indent=2)}

RULES FOR TOOLS:
You may think out loud and converse normally. 
However, if you need to perform an action or get data to answer about something you are not sure about,
AND you have a tool for it, you MUST use this exact plain text format on new lines:

TOOL: <tool_name>
<arg_name>: <arg_value>
END OF RESPONSE

Example:
I need to check the time to answer this.
TOOL: get_system_time
END OF RESPONSE

Example with arguments:
I will turn off the lights now.
TOOL: turn_off_lights
room: living_room
END OF RESPONSE
"""

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    buffer = ConversationBuffer(system_prompt=system_prompt, max_tokens=7000)

    run_number = 0

    while True:

        # Compress history if the conversation gets too long to save tokens
        # if messages and len(messages) > 4:
        #     print("\n[Compressing conversation history to save tokens...]\n")
        #     compressed = compress_history(messages, llm)
        #     messages = [
        #         {"role": "system", "content": system_prompt},
        #         {"role": "system", "content": f"Compressed History:\n{compressed}"}
        #     ]

        run_number += 1

        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']:
            print("Shutting down JARVIS...")
            break

        if user_input.strip() == "":
            print("Please enter a valid message.")
            continue
        
        messages.append({"role": "user", "content": user_input})
        buffer.append("user", user_input)

        print("\nJARVIS: I am processing your request...\n")

        thinking_text_options = [
            "Let me think about that...",
            "I need to consider this carefully...",
            "Processing your request...",
            f"{user_input[:30]}... Interesting question, let me analyze it...",
        ]

        # Randomly select a thinking text to make it feel more natural
        random_index = random.randint(0, len(thinking_text_options) - 1)
        stream_speak(thinking_text_options[random_index])
        
        print("\nJARVIS: ", end="", flush=True) # Start the line without a newline
        
        response_text = ""
        sentence_buffer = "" # Buffer to hold the current sentence for TTS

        # Iterate through the generator and print tokens instantly
        # Print what is being sent to the LLM for debugging in a pretty way
        print(f"\n[Debug] Messages sent to LLM:\n{json.dumps(buffer.get_messages(), indent=2)}\n")
        for chunk in llm.generate(buffer.get_messages()):
            print(chunk, end="", flush=True)
            response_text += chunk
            sentence_buffer += chunk

            # check if buffer ends with a sentence-ending punctuation to trigger TTS
            if any(sentence_buffer.endswith(punct) for punct in [".", "!", "?", "\n", "?\n", ".\n", "!\n"]):
                stream_speak(sentence_buffer.strip())
                sentence_buffer = "" # Clear the buffer after speaking
        
        # catch any remaining text in the buffer that wasn't spoken yet
        if sentence_buffer.strip():
            stream_speak(sentence_buffer.strip())
        
        print() # Add a final newline when the stream finishes

        spoken_text = response_text
        if "TOOL:" in spoken_text:
            spoken_text = spoken_text.split("TOOL:")[0].strip() # Only speak the part before the tool call
        
        # if spoken_text:
        #     speak(spoken_text)
        
        # Append the full compiled response to history
        messages.append({"role": "assistant", "content": response_text})
        buffer.append("assistant", response_text)

        # --- NEW: TOOL INTERCEPTOR ---
        tool_call = extract_tool_call(response_text)
        
        # Append the full compiled response to history if there were no tool calls
        if not tool_call:
            messages.append({"role": "assistant", "content": response_text})
            buffer.append("assistant", response_text)

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

                result_messages = [
                    {"role": "system", "content": f"Tool '{tool_name}' returned: {result}\nNow respond to the user based on this result. Feel free to call more tools if needed."},
                ]

                # add all user and assistant messages from the current conversation to the context for the next LLM call, so it can decide to call more tools if needed
                for msg in messages:
                    # make sure role is in the message and is user before adding to the context
                    if "role" in msg and msg["role"] in ["user"]:
                        result_messages.append(msg)
                
                # Feed the result back to the LLM as a system message
                messages.append({"role": "tool", "content": f"Tool '{tool_name}' returned: {result}\nNow respond to the user based on this result."})
                buffer.append("tool", f"Tool '{tool_name}' returned: {result}\nNow respond to the user based on this result.")
                
                # Trigger a second LLM generation to formulate the final answer
                print("JARVIS: ", end="", flush=True)
                final_response = ""
                final_sentence_buffer = ""
                # Print what is being sent to the LLM for debugging in a pretty way
                print(f"\n[Debug] Messages sent to LLM for final response:\n{json.dumps(result_messages, indent=2)}\n")
                for chunk in llm.generate(result_messages):
                    print(chunk, end="", flush=True)
                    final_response += chunk
                    final_sentence_buffer += chunk

                    # check if buffer ends with a sentence-ending punctuation to trigger TTS
                    if any(final_sentence_buffer.endswith(punct) for punct in [".", "!", "?", "\n", "?\n", ".\n", "!\n"]):
                        stream_speak(final_sentence_buffer.strip())
                        final_sentence_buffer = "" # Clear the buffer after speaking
                print()



                # speak(final_response)
                
                # Save the final response to history
                messages.append({"role": "assistant", "content": final_response})
            else:
                print(f"\n[Error: LLM tried to call a non-existent tool: {tool_name}]")
                # Tell the LLM about the error so it can try again if it wants
                error_message = f"Error: tool '{tool_name}' does not exist. Available tools are: {list(registry.tools.keys())}"
                messages.append({"role": "tool", "content": error_message})
                buffer.append("system", error_message)

                error_response = [
                    {"role": "system", "content": error_message},
                    {"role": "user", "content": user_input}
                ]

                print(f"\n[Debug] Messages sent to LLM after tool error:\n{json.dumps(error_response, indent=2)}\n")
                for chunk in llm.generate(error_response):
                    print(chunk, end="", flush=True)

if __name__ == "__main__":
    main()