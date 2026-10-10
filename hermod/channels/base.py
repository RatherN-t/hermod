"""Channel boundary. The agent only ever sees IncomingMessage and calls Channel.

Adding a messaging provider means writing one new class.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class IncomingMessage:
    sender_id: str  # Telegram chat id (console: the patient's phone)
    text: str
    message_id: str
    media_url: str | None = None  # e.g. a prescription photo
    raw: dict = field(default_factory=dict)


class Channel(Protocol):
    async def send_text(self, to: str, text: str) -> str:
        """Send a message; returns the provider's message id."""
        ...
