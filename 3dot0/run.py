#!/usr/bin/env python3
"""
JARVIS v3.0 — Entry point
Run from the 3dot0/ directory:
    python run.py
"""
import os
import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

os.chdir(_HERE)

import uvicorn
from app.config import load_config

if __name__ == "__main__":
    cfg = load_config()
    server = cfg.get("server", {})
    uvicorn.run(
        "app.main:app",
        host=server.get("host", "0.0.0.0"),
        port=server.get("port", 8000),
        reload=server.get("reload", False),
    )
