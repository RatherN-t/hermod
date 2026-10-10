from functools import lru_cache

from hermod.channels.base import Channel
from hermod.config import get_settings


@lru_cache
def get_channel() -> Channel:
    settings = get_settings()
    if settings.channel == "console":
        from hermod.channels.console import ConsoleChannel

        return ConsoleChannel()
    from hermod.channels.telegram import TelegramChannel

    return TelegramChannel(settings)


def patient_address(patient) -> str:
    """Where the active channel delivers to this patient."""
    if get_settings().channel == "telegram":
        return patient.telegram_chat_id or ""
    return patient.phone
