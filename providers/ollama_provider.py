import requests
from typing import List, Dict, Any
from core.llm_provider import BaseLLM

class OllamaProvider(BaseLLM):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def generate(self, messages: List[Dict[str, Any]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False # Set to false to get the complete response at once
        }
        
        try:
            response = requests.post(self.base_url, json=payload)
            response.raise_for_status() # Raise an exception for bad status codes
            data = response.json()
            return data.get("message", {}).get("content", "")
        except requests.exceptions.HTTPError as e:
            # This catches errors where Ollama is reached, but returns a 400 or 404 (like missing model)
            return f"HTTP Error from Ollama: {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
            # This catches actual connection failures
            return f"Error: Could not connect to Ollama at {self.base_url}. Details: {str(e)}"