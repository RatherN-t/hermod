"""Telegram Bot API adapter. Docs: core.telegram.org/bots/api

Inbound uses long polling (getUpdates), so no public URL or tunnel is needed. Patients are
addressed by chat id; they link their chat to their record via t.me/<bot>?start=<link_code>.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from hermod.channels.base import IncomingMessage
from hermod.config import Settings

log = logging.getLogger(__name__)

POLL_TIMEOUT = 25  # seconds Telegram holds a getUpdates request open


class TelegramChannel:
    def __init__(self, settings: Settings):
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    async def _call(self, method: str, http_timeout: float = 15, **params) -> dict:
        async with httpx.AsyncClient(timeout=http_timeout) as client:
            r = await client.post(f"{self.base_url}/{method}", json=params)
        body = r.json()
        if not body.get("ok"):
            # Don't log the URL: it contains the bot token.
            raise RuntimeError(f"Telegram {method} failed: {body.get('description')}")
        return body["result"]

    async def send_text(self, to: str, text: str) -> str:
        msg = await self._call("sendMessage", chat_id=to, text=text)
        return f"tg-{msg['chat']['id']}-{msg['message_id']}"

    async def typing(self, chat_id: str) -> None:
        try:
            await self._call("sendChatAction", chat_id=chat_id, action="typing")
        except (httpx.HTTPError, RuntimeError):
            log.debug("typing indicator failed", exc_info=False)  # cosmetic

    async def bot_username(self) -> str:
        return (await self._call("getMe"))["username"]

    def parse_update(self, payload: dict) -> list[IncomingMessage]:
        """Turn one Telegram Update into messages. Edits, joins etc. are ignored."""
        m = payload.get("message")
        if not m or "chat" not in m:
            return []
        if m["chat"].get("type") != "private":
            return []  # Hermod only talks 1:1
        chat_id = str(m["chat"]["id"])
        text = m.get("text") or m.get("caption") or ""
        photo = m.get("photo")
        return [IncomingMessage(
            sender_id=chat_id,
            text=text,
            message_id=f"tg-{chat_id}-{m['message_id']}",
            media_url=photo[-1]["file_id"] if photo else None,
            raw=m,
        )]

    async def poll_forever(self, handle: Callable[[IncomingMessage], Awaitable[None]]) -> None:
        """Long-poll getUpdates and hand each message to `handle`, one at a time."""
        await self._call("deleteWebhook")  # getUpdates doesn't work while a webhook is set
        offset = None
        while True:
            try:
                updates = await self._call("getUpdates", http_timeout=POLL_TIMEOUT + 10,
                                           offset=offset, timeout=POLL_TIMEOUT,
                                           allowed_updates=["message"])
            except (httpx.HTTPError, RuntimeError, ValueError) as e:
                # Type only: httpx error messages include the URL, which holds the bot token.
                log.warning("Telegram poll failed (%s); retrying in 5s", type(e).__name__)
                await asyncio.sleep(5)
                continue
            for u in updates:
                offset = u["update_id"] + 1
                for msg in self.parse_update(u):
                    await self.typing(msg.sender_id)
                    try:
                        await handle(msg)
                    except Exception:
                        log.exception("handling Telegram message %s failed", msg.message_id)
