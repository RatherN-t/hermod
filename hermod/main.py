from contextlib import asynccontextmanager

from fastapi import FastAPI

from hermod.channels.routes import router as whatsapp_router
from hermod.dashboard.routes import router as dashboard_router
from hermod.db.session import init_db
from hermod.scheduler import jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    jobs.start()
    yield
    jobs.shutdown()


app = FastAPI(title="Hermod", lifespan=lifespan)
app.include_router(whatsapp_router)
app.include_router(dashboard_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
