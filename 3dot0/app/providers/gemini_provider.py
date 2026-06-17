import json
from typing import Any, Dict, Generator, List, Optional

from google import genai
from google.genai import types

from app.core.llm_provider import BaseLLM, StreamChunk, TokenUsage, ToolCall


class GeminiProvider(BaseLLM):
    """
    LLM provider backed by the official Google GenAI SDK.
    Uses native tool-calling support and parses standard OpenAI-style messages.
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        options: Optional[dict] = None,
    ) -> None:
        self.model = model
        self.options = options or {}
        # genai.Client automatically reads the GEMINI_API_KEY environment variable.
        # Passing an explicit key here overrides the environment variable.
        self._client = genai.Client(api_key=api_key)

    def _parse_messages(self, messages: List[Dict[str, Any]]):
        """Converts standard OpenAI/Ollama messages to Gemini's types.Content structures."""
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content") or ""

            # Gemini handles system prompts via config, not in the turn history
            if role == "system":
                if system_instruction is None:
                    system_instruction = content
                else:
                    system_instruction += "\n" + content
                continue

            parts = []
            if content:
                parts.append(types.Part.from_text(text=content))

            if role == "assistant":
                # Handle Assistant Tool Calls
                if "tool_calls" in msg and msg["tool_calls"]:
                    for tc in msg["tool_calls"]:
                        func = tc.get("function", {})
                        name = func.get("name", "")
                        args = func.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}

                        thought_sig = tc.get("thought_signature")
                        fc_part = types.Part.from_function_call(name=name, args=args)

                        if thought_sig:
                            # Reconstruct the Part with the thought_signature so the
                            # model can recover its internal reasoning context.
                            # NOTE: Do NOT merge signature Parts — one Part per call.
                            try:
                                fc_part = types.Part(
                                    function_call=fc_part.function_call,
                                    thought_signature=thought_sig,
                                )
                            except Exception:
                                pass  # SDK version may not support this construction

                        parts.append(fc_part)
                contents.append(types.Content(role="model", parts=parts))

            elif role in ("tool", "function"):
                # Handle Tool Responses
                name = msg.get("name", "unknown_tool")
                try:
                    response_dict = json.loads(content)
                except Exception:
                    response_dict = {"result": content}

                kwargs = {"name": name, "response": response_dict}
                if "tool_call_id" in msg:
                    kwargs["id"] = msg["tool_call_id"]
                    
                parts.append(types.Part.from_function_response(**kwargs))
                # Gemini expects tool responses to act as user inputs resolving the model's request
                contents.append(types.Content(role="user", parts=parts))

            elif role == "user":
                contents.append(types.Content(role="user", parts=parts))

        return system_instruction, contents

    def _process_response(self, response: Any, done: bool = False) -> StreamChunk:
        """Helper to extract text and native tool calls from a Gemini response/chunk."""
        content = ""
        tool_calls = None
        usage = None

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if getattr(part, "text", None):
                    content += part.text
                elif getattr(part, "function_call", None):
                    if tool_calls is None:
                        tool_calls = []
                    
                    fc = part.function_call
                    # Extract arguments safely as a dictionary
                    args = fc.args if isinstance(fc.args, dict) else dict(fc.args) if fc.args else {}

                    # Capture ID and thought_signature for thinking models.
                    # These must be echoed back verbatim in subsequent turns.
                    fc_id = getattr(fc, "id", None)
                    thought_sig = getattr(part, "thought_signature", None)

                    tool_calls.append(
                        ToolCall(
                            name=fc.name,
                            arguments=args,
                            id=fc_id,
                            thought_signature=thought_sig,
                        )
                    )

        # Capture token usage from usage_metadata (populated on final/non-streaming responses)
        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            usage = TokenUsage(
                prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(meta, "thoughts_token_count", 0) or 0,
            )

        return StreamChunk(content=content, tool_calls=tool_calls, done=done, usage=usage)

    # ── BaseLLM interface ─────────────────────────────────────────────────────

    def generate(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        sys_inst, contents = self._parse_messages(messages)
        config = types.GenerateContentConfig(
            system_instruction=sys_inst,
            **self.options
        )
        try:
            response_stream = self._client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )
            for chunk in response_stream:
                try:
                    if chunk.text:
                        yield chunk.text
                except ValueError:
                    # Occurs if content is blocked by safety settings
                    continue
        except Exception as exc:
            yield f"\n[Gemini error: {exc}]"

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> StreamChunk:
        sys_inst, contents = self._parse_messages(messages)
        config_args = {"system_instruction": sys_inst} if sys_inst else {}
        
        # Map standard tools strictly to Gemini's Tool declarations
        if tools:
            gemini_tools = [t["function"] for t in tools if "function" in t]
            if gemini_tools:
                config_args["tools"] = [types.Tool(function_declarations=gemini_tools)]
                
        config_args.update(self.options)
        config = types.GenerateContentConfig(**config_args)

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return self._process_response(response, done=True)
        except Exception as exc:
            return StreamChunk(content=f"\n[Gemini error: {exc}]", done=True)

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> Generator[StreamChunk, None, None]:
        sys_inst, contents = self._parse_messages(messages)
        config_args = {"system_instruction": sys_inst} if sys_inst else {}
        
        if tools:
            gemini_tools = [t["function"] for t in tools if "function" in t]
            if gemini_tools:
                config_args["tools"] = [types.Tool(function_declarations=gemini_tools)]
                
        config_args.update(self.options)
        config = types.GenerateContentConfig(**config_args)

        try:
            response_stream = self._client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )
            
            # Buffer by one chunk to correctly apply the done=True flag on the last chunk
            iterator = iter(response_stream)
            try:
                prev_chunk = next(iterator)
            except StopIteration:
                return

            for chunk in iterator:
                yield self._process_response(prev_chunk, done=False)
                prev_chunk = chunk
                
            yield self._process_response(prev_chunk, done=True)
            
        except Exception as exc:
            yield StreamChunk(content=f"\n[Gemini error: {exc}]", done=True)

    def test_connection(self) -> bool:
        """Verify the API key and model availability."""
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents="ping"
            )
            return bool(response.text)
        except Exception:
            return False