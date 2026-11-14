"""Background polling for new matching inbox messages."""
from __future__ import annotations

import asyncio
import imaplib
import logging

from app.config import Settings
from app.ingest.email import read_matching_emails

logger = logging.getLogger(__name__)


async def watch_email_inbox(settings: Settings) -> None:
    """Poll IMAP until cancelled, logging each matching message received."""
    started_message = (
        f"Email watcher started: folder={settings.email_imap_folder} "
        f"subject contains {settings.email_subject_filter!r} "
        f"interval={settings.email_poll_interval_s}s"
    )
    logger.info(started_message)
    print(started_message, flush=True)
    while True:
        try:
            print("\rChecking Gmail inbox for VISA emails...   ", end="", flush=True)
            messages = await asyncio.to_thread(read_matching_emails, settings)
            poll_message = f"Gmail inbox checked: {len(messages)} matching VISA email(s)"
            print(f"\r{poll_message}   ", end="", flush=True)
        except (OSError, RuntimeError, ValueError, imaplib.IMAP4.error) as exc:
            message = f"Email watcher poll failed: {exc}"
            logger.error(message)
            print(message, flush=True)
        await asyncio.sleep(settings.email_poll_interval_s)
