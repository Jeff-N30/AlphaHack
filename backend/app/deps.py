"""FastAPI dependency helpers (auth, DB session — filled in later prompts)."""
from __future__ import annotations

from app.config import Settings, get_settings


def settings() -> Settings:
    return get_settings()
