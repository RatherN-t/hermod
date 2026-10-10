"""Fan out new flags to the doctor (optional n8n webhook)."""
from hermod.db.models import Flag


async def notify_doctor(flag: Flag) -> None:
    raise NotImplementedError
