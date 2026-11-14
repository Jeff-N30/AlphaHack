"""Read matching email attachments from an IMAP inbox."""
from __future__ import annotations

import email
import imaplib
import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from app.config import Settings
from app.extract.llm import extract_structured
from app.ingest.render import allowed_suffix, read_preview

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SavedEmail:
    uid: str
    subject: str
    sender: str
    received_at: str
    files: tuple[str, ...]
    person_name: str = "unknown"
    source: str = "subject_filter"
    translation: str = ""
    error: str | None = None


class InboxTriage(BaseModel):
    """LLM-only inbox interpretation; it never decides visa rule outcomes."""

    related: bool = Field(description="Whether this mail or its documents relate to a visa/travel file.")
    person_name: str = Field(
        default="unknown",
        description="Applicant/person name found in the mail or document text; use unknown if absent.",
    )
    reason: str = Field(description="Short evidence-based reason for the relevance decision.")
    translation: str = Field(
        default="",
        description="Concise English translation or summary of the relevant text, preserving names and document types.",
    )


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


def _safe_folder_name(name: str, uid: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip()).strip("._-")
    return f"{cleaned or 'unknown'}_{uid}"


def _name_hint(text: str) -> str:
    for pattern in (
        r"(?im)^\s*(?:applicant|full\s+name|passenger|traveler|traveller|name)\s*[:\-]\s*([^\r\n,]{2,80})",
        r"(?im)\b(?:my\s+name\s+is|i\s+am|this\s+is)\s+([A-Za-z][A-Za-z' -]{2,80})",
        r"(?im)^\s*dear\s+(mr\.?|mrs\.?|ms\.?)?\s*([A-Za-z][A-Za-z' -]{2,80})",
    ):
        match = re.search(pattern, text)
        if match:
            value = match.group(match.lastindex or 1).strip()
            if value:
                return value
    return "unknown"


def _visa_person_name(message_text: str, files: list[Path]) -> str:
    try:
        return _name_hint(_document_context(message_text, files, max_chars=20_000))
    except Exception:
        return _name_hint(message_text)


def _document_context(message_text: str, files: list[Path], *, max_chars: int = 30_000) -> str:
    chunks = [f"EMAIL BODY:\n{message_text[:10_000]}"]
    for path in files:
        chunks.append(f"\nATTACHMENT NAME: {path.name}")
        if not allowed_suffix(path):
            continue
        preview = read_preview(path, max_pages=4)
        if preview.text:
            chunks.append(f"ATTACHMENT TEXT ({path.name}):\n{preview.text[:8_000]}")
    return "\n".join(chunks)[:max_chars]


def _triage_message(
    *,
    message_text: str,
    files: list[Path],
    settings: Settings,
) -> InboxTriage:
    context = _document_context(message_text, files)
    return extract_structured(
        schema=InboxTriage,
        system=(
            "You triage and translate incoming email for a visa-document intake system. "
            "Read OCR text, PDF text, image text, attachment names, and plain email text. "
            "Understand English, French, Arabic, and Arabic transliteration, including spelling "
            "mistakes. Treat these as travel signals when they appear in context: visa, VISA, "
            "visas, visa application, France-Visas, Schengen, embassy, consulate, TLScontact, "
            "passport, laissez-passer, سفر, تأشيرة, فيزا, جواز, سفارة, شنغن, hôtel/hotel, "
            "billet/ticket/flight, réservation/booking, assurance/insurance, attestation, "
            "relevé bancaire/bank statement, salaire/salary, emploi/employment, congé/leave, "
            "itinéraire/itinerary, invitation, hébergement/accommodation, and insurance. "
            "Mark related only when the mail or a document concerns a visa, passport, travel "
            "application, or a supporting document. Ignore newsletters, promotions, unrelated "
            "work, and personal mail. Extract the applicant/person name from supplied text, "
            "not the sender address or attachment filename. Do not invent a name. Translate "
            "or summarize relevant non-English text into English in translation."
        ),
        user=context,
        step="email:triage",
        content_for_cache=context,
        settings=settings,
    )


def _write_message_files(
    *,
    message: Message,
    raw_message: bytes,
    directory: Path,
) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / "message.eml"
    raw_path.write_bytes(raw_message)
    body_path = directory / "body.txt"
    body = _text_body(message)
    body_path.write_text(body, encoding="utf-8")
    files: list[Path] = [raw_path, body_path]
    for part in message.walk():
        filename = part.get_filename()
        if not filename or part.get_content_maintype() == "multipart":
            continue
        path = directory / _safe_filename(_decode(filename))
        path.write_bytes(part.get_payload(decode=True) or b"")
        files.append(path)
    return files


def _mark_seen(mailbox: imaplib.IMAP4_SSL, uid: str) -> None:
    status, _ = mailbox.uid("store", uid, "+FLAGS", "(\\Seen)")
    if status != "OK":
        raise RuntimeError(f"Could not mark email UID {uid} as read.")


def _message_datetime(message: Message) -> datetime | None:
    value = message.get("Date")
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _internal_datetime(fetched: list[object]) -> datetime | None:
    for item in fetched:
        if not isinstance(item, tuple) or not item or not isinstance(item[0], bytes):
            continue
        match = re.search(rb'INTERNALDATE "([^"]+)"', item[0])
        if not match:
            continue
        try:
            return datetime.strptime(
                match.group(1).decode("ascii"),
                "%d-%b-%Y %H:%M:%S %z",
            ).astimezone(timezone.utc)
        except (UnicodeDecodeError, ValueError):
            return None
    return None


def read_matching_emails(
    settings: Settings,
    *,
    imap_factory: Callable[..., imaplib.IMAP4_SSL] = imaplib.IMAP4_SSL,
    started_after: datetime | None = None,
    max_messages: int | None = None,
) -> list[SavedEmail]:
    """Process new inbox messages sequentially and save only visa-related messages."""
    if not settings.email_imap_host or not settings.email_imap_user or not settings.email_imap_password:
        raise ValueError(
            "Email is not configured. Set EMAIL_IMAP_HOST, EMAIL_IMAP_USER, and EMAIL_IMAP_PASSWORD."
        )

    output_dir = settings.data_dir / "email_inbox"
    output_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = output_dir / ".pending"
    staging_dir.mkdir(exist_ok=True)
    mailbox = imap_factory(
        settings.email_imap_host,
        settings.email_imap_port,
        timeout=settings.email_connection_timeout_s,
    )
    saved: list[SavedEmail] = []
    selected = False
    processed_count = 0
    try:
        mailbox.login(settings.email_imap_user, settings.email_imap_password)
        status, _ = mailbox.select(settings.email_imap_folder, readonly=False)
        if status != "OK":
            raise RuntimeError(f"Could not select IMAP folder {settings.email_imap_folder!r}.")
        selected = True
        # Unread-only still includes SUBJECT matches — Gmail often marks mail \Seen
        # as soon as it is opened, which used to drop real VISA intakes.
        filt = (settings.email_subject_filter or "").strip()
        if settings.email_read_unread_only and filt:
            criteria_parts = ["OR", "UNSEEN", "SUBJECT", filt]
        elif settings.email_read_unread_only:
            criteria_parts = ["UNSEEN"]
        else:
            criteria_parts = ["ALL"]
        if started_after is not None:
            criteria_parts.extend(
                ("SINCE", started_after.astimezone(timezone.utc).strftime("%d-%b-%Y"))
            )
        criteria = tuple(criteria_parts)
        status, data = mailbox.uid("search", None, *criteria)
        if status != "OK":
            raise RuntimeError("Could not search the email inbox.")

        processed_uids_path = output_dir / "processed_uids.txt"
        already: set[str] = set()
        if processed_uids_path.exists():
            already = {
                line.strip()
                for line in processed_uids_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }

        for uid_bytes in data[0].split():
            if max_messages is not None and processed_count >= max_messages:
                break
            uid = uid_bytes.decode("ascii")
            if uid in already:
                continue
            status, fetched = mailbox.uid("fetch", uid, "(INTERNALDATE RFC822)")
            if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                raise RuntimeError(f"Could not fetch email UID {uid}.")
            raw_message = fetched[0][1]
            message: Message = email.message_from_bytes(raw_message)
            received_at = _internal_datetime(fetched) or _message_datetime(message)
            if started_after is not None and (
                received_at is None or received_at <= started_after.astimezone(timezone.utc)
            ):
                continue
            subject = _decode(message.get("Subject"))
            subject_match = _subject_matches(subject, settings.email_subject_filter)
            if not subject_match:
                body = _text_body(message)
                stage_dir = staging_dir / uid
                if stage_dir.exists():
                    shutil.rmtree(stage_dir)
                staged_files = _write_message_files(
                    message=message,
                    raw_message=raw_message,
                    directory=stage_dir,
                )
                try:
                    triage = _triage_message(
                        message_text=body,
                        files=staged_files[2:],
                        settings=settings,
                    )
                except Exception as exc:
                    shutil.rmtree(stage_dir)
                    logger.error("Llama triage failed for email UID %s: %s", uid, exc)
                    continue
                if not triage.related:
                    shutil.rmtree(stage_dir)
                    _mark_seen(mailbox, uid)
                    processed_count += 1
                    continue
                person_name = triage.person_name
                source = "llama_triage"
                (stage_dir / "triage.json").write_text(
                    json.dumps(triage.model_dump(mode="json"), indent=2),
                    encoding="utf-8",
                )
                review_dir = output_dir / "needs_review"
                review_dir.mkdir(parents=True, exist_ok=True)
                email_dir = review_dir / _safe_folder_name(person_name, uid)
            else:
                body = _text_body(message)
                source = "subject_filter"
                stage_dir = staging_dir / uid
                if stage_dir.exists():
                    shutil.rmtree(stage_dir)
                staged_files = _write_message_files(
                    message=message,
                    raw_message=raw_message,
                    directory=stage_dir,
                )
                person_name = _visa_person_name(body, staged_files[2:])
                triage = None
                email_dir = output_dir / _safe_folder_name(person_name, uid)

            if email_dir.exists():
                shutil.rmtree(email_dir)
            shutil.move(str(stage_dir), str(email_dir))
            _mark_seen(mailbox, uid)
            processed_count += 1
            already.add(uid)
            processed_uids_path.write_text(
                "\n".join(sorted(already)) + "\n", encoding="utf-8"
            )
            filenames = [
                str(email_dir / "message.eml"),
                str(email_dir / "body.txt"),
                *(
                    str(path)
                    for path in sorted(email_dir.iterdir())
                    if path.name not in {"message.eml", "body.txt"}
                ),
            ]
            received_message = f"Related email received: subject={subject!r} sender={message.get('From', '')}"
            safe_message = received_message.encode("ascii", "backslashreplace").decode("ascii")
            print(f"\r{safe_message}   ", flush=True)
            saved.append(
                SavedEmail(
                    uid=uid,
                    subject=subject,
                    sender=_decode(message.get("From")),
                    received_at=_decode(message.get("Date")),
                    files=tuple(filenames),
                    person_name=person_name,
                    source=source,
                    translation=triage.translation if triage is not None else "",
                )
            )
        return saved
    finally:
        if selected:
            mailbox.close()
        mailbox.logout()
