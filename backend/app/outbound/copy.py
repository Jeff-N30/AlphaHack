"""Copy-to-clipboard / desk delivery stub (no WhatsApp, no auto-send)."""
from __future__ import annotations

from typing import Any


def deliver_copy(*, body: str, application_id: str, officer: str) -> dict[str, Any]:
    """Record that Gloria confirmed a send-back body for copy/email by hand."""
    return {
        "channel": "copy",
        "delivered": True,
        "application_id": application_id,
        "officer": officer,
        "body_chars": len(body),
        "note": "Body ready for Gloria to paste into email — not auto-sent.",
    }
