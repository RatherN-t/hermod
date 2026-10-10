"""Fan out new flags to the doctor (optional n8n webhook)."""
import logging

import httpx

from hermod.config import get_settings
from hermod.db.models import Flag

log = logging.getLogger(__name__)


async def notify_doctor(flag: Flag) -> None:
    url = get_settings().n8n_alert_webhook_url
    if not url:
        return
    payload = {
        "flag_id": flag.id,
        "patient_id": flag.patient_id,
        "kind": flag.kind,
        "severity": str(flag.severity),
        "summary": flag.summary,
        "created_at": flag.created_at.isoformat() if flag.created_at else None,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            (await client.post(url, json=payload)).raise_for_status()
    except httpx.HTTPError:
        # Alerts are best-effort; the flag is already on the dashboard.
        log.exception("n8n alert failed for flag %s", flag.id)
