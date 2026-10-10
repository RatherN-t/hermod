"""Channel boundary. The agent only ever sees IncomingMessage and calls Channel.

Swapping WhatsApp providers (Meta -> WAHA/Twilio) means writing one new class.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class IncomingMessage:
    from_phone: str
    text: str
    message_id: str
    media_url: str | None = None  # e.g. a prescription photo
    raw: dict = field(default_factory=dict)


class Channel(Protocol):
    async def send_text(self, to_phone: str, text: str) -> str:
        """Free-form message. Only allowed within 24h of the patient's last message."""
        ...

    async def send_template(self, to_phone: str, template: str, params: list[str]) -> str:
        """Pre-approved template. Required to open a conversation outside the 24h window."""
        ...

    def parse_webhook(self, payload: dict) -> list[IncomingMessage]: ...
