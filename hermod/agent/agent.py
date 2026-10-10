"""Agent loop: build context -> traced LLM call -> run tools -> guardrail -> reply."""
from hermod.channels.base import IncomingMessage


async def handle_inbound(msg: IncomingMessage) -> None:
    raise NotImplementedError


async def run_checkin(dose_event_id: int) -> None:
    """Scheduler entrypoint: proactively ask about a dose that's due."""
    raise NotImplementedError
