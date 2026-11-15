"""One-time confirm tokens bound to application_id + action (120 s TTL)."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from threading import Lock

TOKEN_TTL_S = 120


@dataclass
class ConfirmToken:
    token: str
    application_id: str
    action: str
    officer: str
    expires_at: float
    used: bool = False


_store: dict[str, ConfirmToken] = {}
_lock = Lock()


class TokenError(Exception):
    """Invalid, expired, or already-used confirm token."""

    def __init__(self, message: str, *, conflict: bool = False) -> None:
        super().__init__(message)
        self.conflict = conflict


def issue_confirm_token(
    *,
    application_id: str,
    action: str,
    officer: str = "Vera",
    ttl_s: int = TOKEN_TTL_S,
) -> ConfirmToken:
    action = action.lower().strip()
    token = secrets.token_urlsafe(24)
    row = ConfirmToken(
        token=token,
        application_id=application_id,
        action=action,
        officer=officer,
        expires_at=time.time() + ttl_s,
    )
    with _lock:
        _store[token] = row
    return row


def consume_confirm_token(
    token: str,
    *,
    application_id: str,
    action: str,
) -> ConfirmToken:
    action = action.lower().strip()
    with _lock:
        row = _store.get(token)
        if row is None:
            raise TokenError("unknown or expired confirm token")
        if row.used:
            raise TokenError("confirm token already used", conflict=True)
        if time.time() > row.expires_at:
            row.used = True
            raise TokenError("confirm token expired", conflict=True)
        if row.application_id != application_id or row.action != action:
            raise TokenError("confirm token does not match application/action")
        row.used = True
        return row


def clear_tokens_for_tests() -> None:
    with _lock:
        _store.clear()
