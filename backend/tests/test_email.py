from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from app.config import Settings
from app.ingest.email import read_matching_emails


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


def test_reads_matching_email_attachments(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        email_imap_host="imap.example.com",
        email_imap_user="user",
        email_imap_password="app-password",
    )
    messages = read_matching_emails(settings, imap_factory=FakeIMAP)
    assert len(messages) == 1
    assert messages[0].subject == "VISA application"
    assert Path(messages[0].files[0]).name == "message.eml"
    assert Path(messages[0].files[1]).read_text(encoding="utf-8") == "Please review my visa application.\n"
    assert Path(messages[0].files[2]).read_bytes() == b"fake pdf"
