"""Read matching email attachments from an IMAP inbox."""
from __future__ import annotations

import email
import imaplib
import logging
import re
from dataclasses import dataclass
from email.header import decode_header
from email.message import Message
from pathlib import Path
from typing import Callable

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SavedEmail:
    uid: str
    subject: str
    sender: str
    received_at: str
    files: tuple[str, ...]


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)
    return cleaned or "attachment"


def _subject_matches(subject: str, expected: str) -> bool:
    return expected.strip().casefold() in subject.casefold()


def _text_body(message: Message) -> str:
    parts: list[str] = []
    for part in message.walk():
        if part.get_content_type() != "text/plain" or part.get_filename():
            continue
        payload = part.get_payload(decode=True)
        if payload:
            parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    return "\n\n".join(parts)


def read_matching_emails(
    settings: Settings,
    *,
    imap_factory: Callable[..., imaplib.IMAP4_SSL] = imaplib.IMAP4_SSL,
) -> list[SavedEmail]:
    """Save attachments from unread emails whose subject contains the configured filter."""
    if not settings.email_imap_host or not settings.email_imap_user or not settings.email_imap_password:
        raise ValueError(
            "Email is not configured. Set EMAIL_IMAP_HOST, EMAIL_IMAP_USER, and EMAIL_IMAP_PASSWORD."
        )

    output_dir = settings.data_dir / "email_inbox"
    output_dir.mkdir(parents=True, exist_ok=True)
    mailbox = imap_factory(
        settings.email_imap_host,
        settings.email_imap_port,
        timeout=settings.email_connection_timeout_s,
    )
    saved: list[SavedEmail] = []
    selected = False
    try:
        mailbox.login(settings.email_imap_user, settings.email_imap_password)
        status, _ = mailbox.select(settings.email_imap_folder, readonly=False)
        if status != "OK":
            raise RuntimeError(f"Could not select IMAP folder {settings.email_imap_folder!r}.")
        selected = True
        criteria = ("UNSEEN", "HEADER", "Subject", settings.email_subject_filter)
        if not settings.email_read_unread_only:
            criteria = criteria[1:]
        status, data = mailbox.uid("search", None, *criteria)
        if status != "OK":
            raise RuntimeError("Could not search the email inbox.")

        for uid_bytes in data[0].split():
            uid = uid_bytes.decode("ascii")
            status, fetched = mailbox.uid("fetch", uid, "(RFC822)")
            if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                raise RuntimeError(f"Could not fetch email UID {uid}.")
            raw_message = fetched[0][1]
            message: Message = email.message_from_bytes(raw_message)
            subject = _decode(message.get("Subject"))
            if not _subject_matches(subject, settings.email_subject_filter):
                continue

            email_dir = output_dir / uid
            email_dir.mkdir(exist_ok=True)
            raw_path = email_dir / "message.eml"
            raw_path.write_bytes(raw_message)
            body_path = email_dir / "body.txt"
            body_path.write_text(_text_body(message), encoding="utf-8")
            filenames: list[str] = [str(raw_path), str(body_path)]
            for part in message.walk():
                filename = part.get_filename()
                if not filename or part.get_content_maintype() == "multipart":
                    continue
                path = email_dir / _safe_filename(_decode(filename))
                path.write_bytes(part.get_payload(decode=True) or b"")
                filenames.append(str(path))
            mailbox.uid("store", uid, "+FLAGS", "(\\Seen)")
            received_message = f"VISA email received: subject={subject!r} sender={message.get('From', '')}"
            safe_message = received_message.encode("ascii", "backslashreplace").decode("ascii")
            print(f"\r{safe_message}   ", flush=True)
            saved.append(
                SavedEmail(
                    uid=uid,
                    subject=subject,
                    sender=_decode(message.get("From")),
                    received_at=_decode(message.get("Date")),
                    files=tuple(filenames),
                )
            )
        return saved
    finally:
        if selected:
            mailbox.close()
        mailbox.logout()
