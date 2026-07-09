from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.db.database import engine, AsyncSessionLocal
from app.db.models import Base
from app.api.routes import html_router, api_router
from app.alerts.dispatcher import check_and_alert

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    scheduler.add_job(
        _run_check,
        IntervalTrigger(minutes=settings.check_interval_minutes),
        id="flood_check",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()


async def _run_check():
    async with AsyncSessionLocal() as session:
        await check_and_alert(session)


app = FastAPI(title="Flood Alert", version="0.1.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, max_age=86400)
app.include_router(html_router)
app.include_router(api_router, prefix="/api")
