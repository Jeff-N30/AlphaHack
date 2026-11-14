"""SMTP delivery for Gloria-confirmed drafts — only imported by lock/actions."""
from __future__ import annotations

import re
import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import Settings, get_settings

_ADDR = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


def extract_email_address(raw: str | None) -> str | None:
    if not raw:
        return None
    m = _ADDR.search(raw)
    return m.group(0).lower() if m else None


def deliver_email(
    *,
    body: str,
    application_id: str,
    officer: str,
    to_address: str,
    subject: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Send applicant message via SMTP (Gmail app password works with IMAP creds)."""
    settings = settings or get_settings()
    to = extract_email_address(to_address)
    if not to:
        raise ValueError("no valid applicant email address")

    user = (settings.email_imap_user or "").strip()
    password = (settings.email_imap_password or "").strip()
    host = getattr(settings, "email_smtp_host", None) or "smtp.gmail.com"
    port = int(getattr(settings, "email_smtp_port", None) or 587)
    if not user or not password:
        raise RuntimeError("EMAIL_IMAP_USER / EMAIL_IMAP_PASSWORD required for SMTP send")

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject or f"Your visa file — {officer}"
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=settings.email_connection_timeout_s) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)

    return {
        "channel": "email",
        "delivered": True,
        "application_id": application_id,
        "officer": officer,
        "to": to,
        "body_chars": len(body),
        "note": "Sent by Gloria confirm (SMTP).",
    }
