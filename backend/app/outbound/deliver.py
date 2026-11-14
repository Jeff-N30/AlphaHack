"""SMTP delivery for Gloria-confirmed drafts — lock/actions only."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.outbound.email_smtp import deliver_email, extract_email_address


class DeliveryError(Exception):
    """Cannot send applicant email (missing address or SMTP failure)."""


def deliver_applicant_message(
    *,
    body: str,
    application_id: str,
    officer: str,
    to_address: str | None,
    subject: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Send via SMTP. Raises DeliveryError if recipient or credentials are missing."""
    settings = settings or get_settings()
    to = extract_email_address(to_address) or extract_email_address(
        settings.demo_applicant_email
    )
    if not to:
        raise DeliveryError(
            "No applicant email — enter the correspondent address before sending."
        )
    user = (settings.email_imap_user or "").strip()
    password = (settings.email_imap_password or "").strip()
    if not user or not password:
        raise DeliveryError(
            "EMAIL_IMAP_USER / EMAIL_IMAP_PASSWORD required to send email."
        )
    try:
        return deliver_email(
            body=body,
            application_id=application_id,
            officer=officer,
            to_address=to,
            subject=subject,
            settings=settings,
        )
    except DeliveryError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DeliveryError(f"SMTP send failed: {exc}") from exc
