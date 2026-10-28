from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes.jobs import applications_router, jobs_router
from .api.routes.matching import router as matching_router
from .api.routes.profile import router as profile_router
from .api.routes.scheduler import scheduler_router
from .api.routes.watchers import (
    archive_router,
    logs_router,
    notifications_router,
    watchers_router,
)
from .core.config import get_settings
from .core.database import init_database
from .core.logging import configure_logging
from .core.scheduler import watcher_scheduler

configure_logging()
settings = get_settings()
init_database()


@asynccontextmanager
async def lifespan(app: FastAPI):
    watcher_scheduler.start()
    try:
        yield
    finally:
        watcher_scheduler.stop()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(matching_router)
app.include_router(profile_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(watchers_router)
app.include_router(archive_router)
app.include_router(notifications_router)
app.include_router(logs_router)
app.include_router(scheduler_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "scheduler": "/api/v1/scheduler/status",
    }
