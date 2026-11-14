"""Background polling for new inbox messages and the VISA pipeline."""
from __future__ import annotations

import asyncio
import imaplib
import logging
from datetime import datetime, timezone

from app.config import Settings
from app.ingest.email_pipeline import process_visa_inbox

logger = logging.getLogger(__name__)


async def watch_email_inbox(settings: Settings) -> None:
    """Poll only post-startup messages, processing at most one per interval."""
    started_message = (
        f"Email watcher started: folder={settings.email_imap_folder} "
        f"subject filter={settings.email_subject_filter!r}; "
        f"new messages only; one per poll; interval={settings.email_poll_interval_s}s"
    )
    logger.info(started_message)
    print(started_message, flush=True)
    started_after = datetime.now(timezone.utc)
    while True:
        try:
            print("\rChecking Gmail inbox for related messages...   ", end="", flush=True)
            batch = await asyncio.to_thread(
                process_visa_inbox,
                settings=settings,
                started_after=started_after,
                max_messages=1,
            )
            count = int(batch.get("count") or 0)
            poll_message = f"Gmail inbox checked: {count} VISA pipeline message(s)"
            print(f"\r{poll_message}   ", end="", flush=True)
            for result in batch.get("results") or []:
                outcome = (result.get("audit") or {}).get("outcome")
                print(
                    f"\nVISA pipeline: uid={result.get('email_uid')} "
                    f"app={result.get('application_id')} outcome={outcome} "
                    f"-> {result.get('human_status')} (human_required=True)",
                    flush=True,
                )
        except (OSError, RuntimeError, ValueError, imaplib.IMAP4.error) as exc:
            message = f"Email watcher poll failed: {exc}"
            logger.error(message)
            print(message, flush=True)
        await asyncio.sleep(settings.email_poll_interval_s)
