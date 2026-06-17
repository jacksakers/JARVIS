"""
JARVIS v3.0 — Model Registry
Catalog of available LLM models with display metadata.
Used by the API, worker, and frontend for model selection.
"""
from typing import Any, Dict, List, Optional


AVAILABLE_MODELS: List[Dict[str, Any]] = [
    {
        "id": "gemma4:e4b",
        "name": "Gemma 4 (Local)",
        "provider": "ollama",
        "description": "Fast and private — runs entirely on your machine. Best for personal tasks, journaling, and routines.",
        "free": True,
        "thinking": False,
        "badge": "Local",
    },
    {
        "id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash",
        "provider": "gemini",
        "description": "Google's fast, capable model. Free tier available with rate limits.",
        "free": True,
        "thinking": False,
        "badge": "Free",
    },
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "provider": "gemini",
        "description": "Thinking model with excellent tool-calling. Great for coding and complex reasoning. Paid.",
        "free": False,
        "thinking": True,
        "badge": "Paid",
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "provider": "gemini",
        "description": "Most capable thinking model. Best for complex multi-step coding tasks. Paid.",
        "free": False,
        "thinking": True,
        "badge": "Paid",
    },
]

# Model IDs that require thought signature handling
THINKING_MODELS = {m["id"] for m in AVAILABLE_MODELS if m.get("thinking")}

# Model IDs that use the Gemini provider
GEMINI_MODEL_IDS = {m["id"] for m in AVAILABLE_MODELS if m["provider"] == "gemini"}


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Return metadata for a model ID, or None if unknown."""
    for m in AVAILABLE_MODELS:
        if m["id"] == model_id:
            return m
    return None


def is_gemini_model(model_id: Optional[str]) -> bool:
    """Return True if the model should use the Gemini provider."""
    if not model_id:
        return False
    return model_id in GEMINI_MODEL_IDS or model_id.startswith("gemini-")


def is_thinking_model(model_id: Optional[str]) -> bool:
    """Return True if this model uses extended thinking (requires thought signature handling)."""
    if not model_id:
        return False
    return model_id in THINKING_MODELS


def create_llm(model_id: Optional[str], cfg: dict):
    """
    Create and return an LLM instance for the given model_id.
    Falls back to the config default if model_id is None.
    """
    from app.providers.gemini_provider import GeminiProvider
    from app.providers.ollama_provider import OllamaProvider

    llm_cfg = cfg.get("llm", {})

    if not model_id:
        model_id = llm_cfg.get("model", "gemma4:e4b")

    if is_gemini_model(model_id):
        return GeminiProvider(
            model=model_id,
            options=llm_cfg.get("gemini_options", {}),
        )
    else:
        return OllamaProvider(
            model=model_id,
            base_url=llm_cfg.get("ollama_url", "http://localhost:11434"),
            options=llm_cfg.get("options", {}),
        )
