from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from app.config import Settings
from app.ingest.email import InboxTriage, read_matching_emails


class FakeIMAP:
    def __init__(self, _host: str, _port: int, **_kwargs: object) -> None:
        self.message = EmailMessage()
        self.message["Subject"] = "VISA application"
        self.message["From"] = "applicant@example.com"
        self.message["Date"] = "Sat, 14 Nov 2026 10:00:00 +0000"
        self.message.set_content("Please review my visa application.")
        self.message.add_attachment(b"fake pdf", maintype="application", subtype="pdf", filename="passport.pdf")
        self.seen: list[str] = []

    def login(self, _user: str, _password: str) -> tuple[str, list[bytes]]:
        return "OK", []

    def select(self, _folder: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        assert readonly is False
        return "OK", []

    def uid(self, command: str, uid: str | None, *args: str):
        if command == "search":
            return "OK", [b"42"]
        if command == "fetch":
            return "OK", [(b"header", self.message.as_bytes())]
        if command == "store":
            self.seen.append(uid or "")
            return "OK", []
        raise AssertionError(command)

    def close(self) -> tuple[str, list[bytes]]:
        return "OK", []

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", []


def test_reads_matching_email_attachments(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        data_dir=tmp_path,
        email_imap_host="imap.example.com",
        email_imap_user="user",
        email_imap_password="app-password",
    )
    monkeypatch.setattr(
        "app.ingest.email._triage_message",
        lambda **_kwargs: InboxTriage(
            related=True,
            person_name="unknown",
            reason="subject-filtered visa email",
            translation="Visa application email.",
        ),
    )
    messages = read_matching_emails(settings, imap_factory=FakeIMAP)
    assert len(messages) == 1
    assert messages[0].subject == "VISA application"
    assert Path(messages[0].files[0]).name == "message.eml"
    assert Path(messages[0].files[1]).read_text(encoding="utf-8") == "Please review my visa application.\n"
    assert Path(messages[0].files[2]).read_bytes() == b"fake pdf"


class NonVisaIMAP(FakeIMAP):
    def __init__(self, _host: str, _port: int, **_kwargs: object) -> None:
        self.message = EmailMessage()
        self.message["Subject"] = "Documents for my trip"
        self.message["From"] = "applicant@example.com"
        self.message["Date"] = "Sat, 14 Nov 2026 10:00:00 +0000"
        self.message.set_content("Applicant: Karim Nassar\nPlease find my passport.")
        self.message.add_attachment(b"fake pdf", maintype="application", subtype="pdf", filename="passport.pdf")
        self.seen = []


def test_llama_fallback_saves_related_nonmatching_email(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        data_dir=tmp_path,
        email_imap_host="imap.example.com",
        email_imap_user="user",
        email_imap_password="app-password",
    )

    def related_triage(**_kwargs: object) -> InboxTriage:
        return InboxTriage(
            related=True,
            person_name="Karim Nassar",
            reason="passport document",
            translation="Passport document found",
        )

    monkeypatch.setattr("app.ingest.email._triage_message", related_triage)
    messages = read_matching_emails(settings, imap_factory=NonVisaIMAP)

    assert len(messages) == 1
    assert messages[0].source == "llama_triage"
    assert messages[0].person_name == "Karim Nassar"
    assert "needs_review" in messages[0].files[0]


def test_llama_fallback_discards_unrelated_email(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        data_dir=tmp_path,
        email_imap_host="imap.example.com",
        email_imap_user="user",
        email_imap_password="app-password",
    )
    monkeypatch.setattr(
        "app.ingest.email._triage_message",
        lambda **_kwargs: InboxTriage(
            related=False,
            person_name="unknown",
            reason="unrelated",
        ),
    )
    assert read_matching_emails(settings, imap_factory=NonVisaIMAP) == []
    assert not list((tmp_path / "email_inbox").rglob("message.eml"))
