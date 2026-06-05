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
        except requests.exceptions.RequestException as e:
            return f"Error: Could not communicate with Ollama at {self.base_url}. Details: {str(e)}"