import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def reset_in_memory_state():
    from app.core.config import get_settings
    from app.core.database import init_database
    from app.core.scheduler import watcher_scheduler
    from app.domains.jobs.repository import jobs_repository
    from app.domains.profile.repository import profile_repository
    from app.domains.watchers.db_repository import db_repository

    settings = get_settings()
    original_scheduler_enabled = settings.scheduler_enabled
    settings.scheduler_enabled = False

    try:
        watcher_scheduler.stop()
        watcher_scheduler._last_run_at = None
        watcher_scheduler._last_run_summary = {}
        watcher_scheduler._runs = []
        watcher_scheduler._running = False

        init_database()
        jobs_repository.clear_all()
        profile_repository.clear_all()
        db_repository.clear_all()
        yield
    finally:
        watcher_scheduler.stop()
        watcher_scheduler._last_run_at = None
        watcher_scheduler._last_run_summary = {}
        watcher_scheduler._runs = []
        watcher_scheduler._running = False
        settings.scheduler_enabled = original_scheduler_enabled
