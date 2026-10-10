"""APScheduler: materialise DoseEvents from prescriptions and fire check-ins on time."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


def start() -> None:
    # TODO(after plan approval): register tick job (every minute) -> due DoseEvents -> run_checkin
    scheduler.start()


def shutdown() -> None:
    scheduler.shutdown(wait=False)
