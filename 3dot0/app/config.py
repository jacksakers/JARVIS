import os
from pathlib import Path
from typing import Any, Dict

import yaml

_HERE = Path(__file__).parent.parent.resolve()
_CONFIG_PATH = _HERE / "config.yaml"

_config_cache: Dict[str, Any] = {}


def load_config(path: Path = _CONFIG_PATH) -> Dict[str, Any]:
    """Load config.yaml and return it as a dict. Result is cached."""
    global _config_cache
    if _config_cache:
        return _config_cache

    try:
        with open(path) as f:
            _config_cache = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"[Config] Warning: {path} not found. Using defaults.")
        _config_cache = {}
    except yaml.YAMLError as exc:
        print(f"[Config] Error parsing {path}: {exc}. Using defaults.")
        _config_cache = {}

    return _config_cache


def get_db_path() -> str:
    cfg = load_config()
    db_path = cfg.get("database", {}).get("path", "jarvis.db")
    if not os.path.isabs(db_path):
        return str(_HERE / db_path)
    return db_path
