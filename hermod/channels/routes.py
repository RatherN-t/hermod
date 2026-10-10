from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from hermod.config import get_settings

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])


@router.get("", response_class=PlainTextResponse)
def verify(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
) -> str:
    """Meta calls this once when you register the webhook URL."""
    if mode == "subscribe" and token == get_settings().whatsapp_verify_token:
        return challenge
    raise HTTPException(status_code=403)


@router.post("")
async def receive(request: Request) -> dict:
    """Inbound messages -> verify signature -> parse -> agent.handle_inbound (async)."""
    # TODO(after plan approval): wire to agent
    return {"status": "ok"}
