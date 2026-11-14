"""VisaRef API — scaffold only (no business logic yet)."""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="VisaRef", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
