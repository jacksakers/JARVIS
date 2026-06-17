"""
JARVIS v3.0 — Model Registry
Catalog of available LLM models with display metadata.
Used by the API, worker, and frontend for model selection.
"""
from typing import Any, Dict, List, Optional


# Pricing in USD per 1,000,000 tokens (input / output).
# Thinking tokens are billed at the output rate.
# Source: Google AI pricing page — update when rates change.
_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro":   {"input": 1.25, "output": 10.00},
    # Gemini 3 series (preview pricing — subject to change)
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3.5-flash":       {"input": 1.50, "output": 9.00},
}

AVAILABLE_MODELS: List[Dict[str, Any]] = [
    {
        "id": "gemma4:e4b",
        "name": "Gemma 4 (Local)",
        "provider": "ollama",
        "description": "Fast and private — runs entirely on your machine. Best for personal tasks, journaling, and routines.",
        "free": True,
        "thinking": False,
        "badge": "Local",
        "pricing": None,
    },
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "provider": "gemini",
        "description": "Quick thinking model with tool-calling. Paid.",
        "free": False,
        "thinking": True,
        "badge": "Paid",
        "pricing": _PRICING["gemini-2.5-flash"],
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "provider": "gemini",
        "description": "Very capable thinking model. Good for complex multi-step coding tasks. Paid.",
        "free": False,
        "thinking": True,
        "badge": "Paid",
        "pricing": _PRICING["gemini-2.5-pro"],
    },
    {
        "id": "gemini-3-flash-preview",
        "name": "Gemini 3 Flash Preview",
        "provider": "gemini",
        "description": "Even more capable quick thinking model. Suitable for testing new features. Paid.",
        "free": False,
        "thinking": True,
        "badge": "Paid",
        "pricing": _PRICING["gemini-3-flash-preview"],
    },
    {
        "id": "gemini-3.1-flash-lite",
        "name": "Gemini 3.1 Flash Lite",
        "provider": "gemini",
        "description": "Efficient thinking model. Good for tasks that need some reasoning but are cost-sensitive. Paid.",
        "free": False,
        "thinking": True,
        "badge": "Paid",
        "pricing": _PRICING["gemini-3.1-flash-lite"],
    }
    {
        "id": "gemini-3.5-flash",
        "name": "Gemini 3.5 Flash",
        "provider": "gemini",
        "description": "The next-generation quick thinking model. Best for testing the latest capabilities. Paid.",
        "free": False,
        "thinking": True,
        "badge": "Paid",
        "pricing": _PRICING["gemini-3.5-flash"],
    }
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


def compute_cost(
    model_id: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
    thinking_tokens: int = 0,
) -> Optional[float]:
    """
    Return estimated cost in USD for a Gemini API call, or None for local models.
    Thinking tokens are billed at the output (candidates) rate.
    """
    if not model_id:
        return None
    pricing = _PRICING.get(model_id)
    if not pricing:
        return None
    input_cost  = prompt_tokens  / 1_000_000 * pricing["input"]
    output_cost = (completion_tokens + thinking_tokens) / 1_000_000 * pricing["output"]
    return round(input_cost + output_cost, 6)


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
