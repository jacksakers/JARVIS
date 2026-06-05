import requests
import json
from typing import List, Dict, Any, Generator
from core.llm_provider import BaseLLM

class OllamaProvider(BaseLLM):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def generate(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True # Changed to True to enable streaming
        }
        
        try:
            # Use stream=True in the requests call
            with requests.post(self.base_url, json=payload, stream=True) as response:
                response.raise_for_status() 
                
                # Iterate over the streaming response line by line
                for line in response.iter_lines():
                    if line:
                        # Ollama sends back JSON on each line
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                            
        except requests.exceptions.HTTPError as e:
            yield f"\nHTTP Error from Ollama: {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
            yield f"\nError: Could not connect to Ollama at {self.base_url}. Details: {str(e)}"