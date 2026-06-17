"""API router: available LLM models."""
from typing import Any, Dict, List

from fastapi import APIRouter

from app.core.model_registry import AVAILABLE_MODELS

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/", response_model=List[Dict[str, Any]])
def list_models():
    """List all available LLM models with display metadata."""
    return AVAILABLE_MODELS
