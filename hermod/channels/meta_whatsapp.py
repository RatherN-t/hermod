"""WhatsApp Cloud API adapter (Meta). Docs: developers.facebook.com/docs/whatsapp/cloud-api"""
from hermod.channels.base import IncomingMessage
from hermod.config import Settings


class MetaWhatsAppChannel:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = (
            f"https://graph.facebook.com/{settings.whatsapp_graph_version}"
            f"/{settings.whatsapp_phone_number_id}/messages"
        )

    async def send_text(self, to_phone: str, text: str) -> str:
        raise NotImplementedError

    async def send_template(self, to_phone: str, template: str, params: list[str]) -> str:
        raise NotImplementedError

    def parse_webhook(self, payload: dict) -> list[IncomingMessage]:
        raise NotImplementedError

    def verify_signature(self, body: bytes, signature_header: str) -> bool:
        """Check X-Hub-Signature-256 with the app secret."""
        raise NotImplementedError
