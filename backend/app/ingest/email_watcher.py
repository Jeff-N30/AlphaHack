"""Background polling for new matching inbox messages."""
from __future__ import annotations

import asyncio
import imaplib
import logging

from app.config import Settings
from app.ingest.email_pipeline import process_visa_inbox

logger = logging.getLogger(__name__)


async def watch_email_inbox(settings: Settings) -> None:
    """Poll IMAP → save VISA mails → OCR/MRZ → Llama extract → TLS rules."""
    started_message = (
        f"Email watcher started: folder={settings.email_imap_folder} "
        f"subject contains {settings.email_subject_filter!r} "
        f"interval={settings.email_poll_interval_s}s "
        f"(full pipeline: ingest + llama + rules)"
    )
    logger.info(started_message)
    print(started_message, flush=True)
    while True:
        try:
            print("\rChecking Gmail inbox for VISA emails...   ", end="", flush=True)
            batch = await asyncio.to_thread(process_visa_inbox, settings=settings)
            n = int(batch.get("count") or 0)
            poll_message = f"Gmail inbox checked: {n} matching VISA email(s) processed"
            print(f"\r{poll_message}   ", end="", flush=True)
            for result in batch.get("results") or []:
                outcome = (result.get("audit") or {}).get("outcome")
                print(
                    f"\nVISA pipeline: uid={result.get('email_uid')} "
                    f"app={result.get('application_id')} outcome={outcome} "
                    f"→ {result.get('human_status')} (human_required=True)",
                    flush=True,
                )
        except (OSError, RuntimeError, ValueError, imaplib.IMAP4.error) as exc:
            message = f"Email watcher poll failed: {exc}"
            logger.error(message)
            print(message, flush=True)
        await asyncio.sleep(settings.email_poll_interval_s)
