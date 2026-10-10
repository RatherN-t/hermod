"""Channel that prints instead of sending. Used with CHANNEL=console and in tests."""
import itertools


class ConsoleChannel:
    def __init__(self, echo: bool = True):
        self.echo = echo
        self.sent: list[dict] = []
        self._ids = itertools.count(1)

    async def send_text(self, to: str, text: str) -> str:
        msg_id = f"console-{next(self._ids)}"
        self.sent.append({"id": msg_id, "to": to, "text": text})
        if self.echo:
            print(f"\n  Hermod -> {to}: {text}\n")
        return msg_id
