from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


def init_database() -> None:
    from ..domains.jobs import models as _jobs_models  # noqa: F401
    from ..domains.profile import models as _profile_models  # noqa: F401
    from ..domains.watchers import models as _watchers_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
