import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hermod.agent.agent import handle_inbound
from hermod.channels import get_channel
from hermod.config import get_settings
from hermod.dashboard.routes import router as dashboard_router
from hermod.db.session import init_db
from hermod.scheduler import jobs

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
# httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    jobs.start()
    poller = None
    if get_settings().channel == "telegram":
        # Long polling: Telegram needs no public URL, so no tunnel.
        poller = asyncio.create_task(get_channel().poll_forever(handle_inbound))
    yield
    if poller:
        poller.cancel()
    jobs.shutdown()


app = FastAPI(title="Hermod", lifespan=lifespan)
app.include_router(dashboard_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
