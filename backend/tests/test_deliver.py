"""Outbound deliver: SMTP required (no silent copy)."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.outbound.deliver import DeliveryError, deliver_applicant_message


def test_deliver_requires_recipient(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        checklist_dir=tmp_path,
        email_imap_user="officer@gmail.com",
        email_imap_password="app-pass",
        demo_applicant_email="",
    )
    with pytest.raises(DeliveryError, match="No applicant email"):
        deliver_applicant_message(
            body="Hello",
            application_id="app-1",
            officer="Gloria",
            to_address=None,
            settings=settings,
        )


def test_deliver_requires_smtp_creds(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        checklist_dir=tmp_path,
        email_imap_user="",
        email_imap_password="",
    )
    with pytest.raises(DeliveryError, match="EMAIL_IMAP"):
        deliver_applicant_message(
            body="Hello",
            application_id="app-1",
            officer="Gloria",
            to_address="karim@example.com",
            settings=settings,
        )


def test_deliver_smtp_success(tmp_path, monkeypatch) -> None:
    settings = Settings(
        data_dir=tmp_path,
        checklist_dir=tmp_path,
        email_imap_user="officer@gmail.com",
        email_imap_password="app-pass",
    )

    def _fake_email(**kwargs):
        return {
            "channel": "email",
            "delivered": True,
            "to": "karim@example.com",
            "application_id": kwargs["application_id"],
            "officer": kwargs["officer"],
            "body_chars": len(kwargs["body"]),
            "note": "Sent by Gloria confirm (SMTP).",
        }

    monkeypatch.setattr("app.outbound.deliver.deliver_email", _fake_email)
    out = deliver_applicant_message(
        body="Hello Karim",
        application_id="app-1",
        officer="Gloria",
        to_address="karim@example.com",
        settings=settings,
    )
    assert out["channel"] == "email"
    assert out["to"] == "karim@example.com"
