from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..domains.jobs.parser import JobParser
from ..domains.jobs.repository import jobs_repository
from ..domains.jobs.service import JobsService
from ..domains.matching.service import HybridMatchingService
from ..domains.profile.repository import profile_repository
from ..domains.watchers.db_repository import db_repository
from ..domains.watchers.discovery import LiveJobDiscoveryService
from ..domains.watchers.schemas import (
    SyncStatus,
    WatcherDiscoverRequest,
)
from ..domains.watchers.service import WatcherService
from .config import Settings, get_settings
from .database import init_database

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WatcherScheduler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._scheduler: BackgroundScheduler | None = None
        self._lock = Lock()
        self._last_run_at: datetime | None = None
        self._last_run_summary: dict[str, Any] = {}
        self._running = False
        self._runs: list[dict[str, Any]] = []

    @property
    def scheduler(self) -> BackgroundScheduler | None:
        return self._scheduler

    @property
    def is_running(self) -> bool:
        return self._running and (self._scheduler.running if self._scheduler else False)

    @property
    def last_run_at(self) -> datetime | None:
        return self._last_run_at

    @property
    def last_run_summary(self) -> dict[str, Any]:
        return dict(self._last_run_summary)

    @property
    def recent_runs(self) -> list[dict[str, Any]]:
        return list(self._runs[-10:])

    def _build_watcher_service(self) -> WatcherService:
        init_database()
        matching_service = HybridMatchingService(settings=self.settings)
        jobs_service = JobsService(
            repository=jobs_repository,
            profile_repository=profile_repository,
            matching_service=matching_service,
            parser=JobParser(),
        )
        return WatcherService(
            repository=db_repository,
            matching_service=matching_service,
            settings=self.settings,
            profile_repository=profile_repository,
            jobs_service=jobs_service,
            discovery_service=LiveJobDiscoveryService(),
        )

    def run_all_active_watchers(self) -> dict[str, Any]:
        started_at = utcnow()
        summary: dict[str, Any] = {
            "started_at": started_at.isoformat(),
            "trigger": "manual",
            "watchers_scanned": 0,
            "watchers_with_urls": 0,
            "watchers_dispatched": 0,
            "watchers_failed": 0,
            "processed_jobs_total": 0,
            "matched_jobs_total": 0,
            "notifications_created_total": 0,
            "inactive_jobs_skipped_total": 0,
            "per_watcher": [],
        }

        try:
            service = self._build_watcher_service()
            watchers = service.list_watchers()
            summary["watchers_scanned"] = len(watchers)
            db_repository.log_event(
                level="INFO",
                source="scheduler",
                message=f"Scheduler sweep başladı · {len(watchers)} watcher tarandı · max_jobs={self.settings.scheduler_max_jobs_per_run}",
                metadata={
                    "watchers": len(watchers),
                    "max_jobs": self.settings.scheduler_max_jobs_per_run,
                    "scheduler_interval_minutes": self.settings.scheduler_interval_minutes,
                },
            )

            for watcher in watchers:
                if not watcher.is_active:
                    continue
                source_urls = self._extract_source_urls(watcher)
                if not source_urls:
                    continue
                summary["watchers_with_urls"] += 1

                try:
                    response = service.discover_jobs(
                        watcher.id,
                        WatcherDiscoverRequest(
                            source_urls=source_urls,
                            triggered_by="scheduler",
                            max_jobs=self.settings.scheduler_max_jobs_per_run,
                        ),
                    )
                    run = response.run
                    metadata = run.metadata or {}
                    summary["watchers_dispatched"] += 1
                    summary["processed_jobs_total"] += int(run.processed_jobs or 0)
                    summary["matched_jobs_total"] += int(run.matched_jobs or 0)
                    summary["notifications_created_total"] += int(
                        run.notifications_created or 0
                    )
                    summary["inactive_jobs_skipped_total"] += int(
                        metadata.get("inactive_jobs_skipped") or 0
                    )
                    summary["per_watcher"].append(
                        {
                            "watcher_id": watcher.id,
                            "query_name": watcher.query_name,
                            "status": run.status.value
                            if isinstance(run.status, SyncStatus)
                            else str(run.status),
                            "processed_jobs": run.processed_jobs,
                            "matched_jobs": run.matched_jobs,
                            "notifications_created": run.notifications_created,
                            "inactive_jobs_skipped": int(
                                metadata.get("inactive_jobs_skipped") or 0
                            ),
                            "error": run.error_message,
                        }
                    )
                except Exception as exc:
                    summary["watchers_failed"] += 1
                    summary["per_watcher"].append(
                        {
                            "watcher_id": watcher.id,
                            "query_name": watcher.query_name,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
                    db_repository.log_event(
                        level="ERROR",
                        source="scheduler",
                        user_id=getattr(watcher, "user_id", None),
                        watcher_id=getattr(watcher, "id", None),
                        message=f"Watcher HATASI · {watcher.id} · {exc.__class__.__name__}: {str(exc)[:200]}",
                        metadata={"error_type": exc.__class__.__name__},
                    )
                    log.exception("Watcher %s scheduled discovery failed", watcher.id)
        except Exception as exc:
            db_repository.log_event(
                level="ERROR",
                source="scheduler",
                message=f"Scheduler sweep GENEL HATA · {exc.__class__.__name__}: {str(exc)[:240]}",
                metadata={"error_type": exc.__class__.__name__},
            )
            log.exception("Scheduled watcher sweep failed")
            summary["error"] = str(exc)
        finally:
            finished_at = utcnow()
            summary["finished_at"] = finished_at.isoformat()
            summary["duration_seconds"] = max(
                0.0, (finished_at - started_at).total_seconds()
            )
            try:
                db_repository.log_event(
                    level="INFO",
                    source="scheduler",
                    message=f"Scheduler sweep bitti · {summary['watchers_dispatched']} çalışan / "
                    f"{summary.get('watchers_failed', 0)} hata · {summary['matched_jobs_total']} match · "
                    f"{summary['notifications_created_total']} bildirim · "
                    f"{summary['duration_seconds']:.1f}s",
                    metadata={k: v for k, v in summary.items() if k != "per_watcher"},
                )
            except Exception:
                logging.exception("BLE001 scheduler: run_all summary log_event yazılamadı")
            with self._lock:
                self._last_run_at = finished_at
                self._last_run_summary = summary
                self._runs.append(summary)
                if len(self._runs) > 50:
                    self._runs = self._runs[-50:]
        return summary

    def run_watcher(self, watcher_id: str) -> dict[str, Any]:
        started_at = utcnow()
        result: dict[str, Any] = {
            "started_at": started_at.isoformat(),
            "watcher_id": watcher_id,
            "trigger": "manual_single",
        }
        service = self._build_watcher_service()
        watcher = service.repository.get_watcher(watcher_id)
        source_urls = self._extract_source_urls(watcher)
        if not source_urls:
            raise ValueError("Bu watcher için kaynak URL'si tanımlı değil.")
        try:
            response = service.discover_jobs(
                watcher.id,
                WatcherDiscoverRequest(
                    source_urls=source_urls,
                    triggered_by="manual_single",
                    max_jobs=self.settings.scheduler_max_jobs_per_run,
                ),
            )
            run = response.run
            metadata = run.metadata or {}
            result.update(
                {
                    "status": run.status.value
                    if isinstance(run.status, SyncStatus)
                    else str(run.status),
                    "processed_jobs": run.processed_jobs,
                    "matched_jobs": run.matched_jobs,
                    "notifications_created": run.notifications_created,
                    "inactive_jobs_skipped": int(
                        metadata.get("inactive_jobs_skipped") or 0
                    ),
                    "source_reports": [
                        report.model_dump(mode="json")
                        if hasattr(report, "model_dump")
                        else dict(report)
                        for report in metadata.get("source_reports") or []
                    ],
                    "source_urls": list(metadata.get("source_urls") or source_urls),
                    "error": run.error_message,
                }
            )
        except Exception as exc:
            log.exception("Manual watcher %s discovery failed", watcher_id)
            result["status"] = "failed"
            result["error"] = str(exc)
        finally:
            finished_at = utcnow()
            result["finished_at"] = finished_at.isoformat()
            result["duration_seconds"] = max(
                0.0, (finished_at - started_at).total_seconds()
            )
        return result

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            if not self.settings.scheduler_enabled:
                log.info(
                    "Scheduler disabled via settings.scheduler_enabled=False; skipping start."
                )
                self._running = False
                return

            self._scheduler = BackgroundScheduler(
                timezone=timezone.utc,
                job_defaults={
                    "coalesce": True,
                    "max_instances": 1,
                    "misfire_grace_time": 300,
                },
            )
            self._scheduler.add_job(
                self.run_all_active_watchers,
                trigger=IntervalTrigger(
                    minutes=self.settings.scheduler_interval_minutes,
                    timezone=timezone.utc,
                ),
                id="watcher_sweep",
                name="Watcher scheduled discovery sweep",
                replace_existing=True,
                next_run_time=utcnow(),
            )
            self._scheduler.start()
            self._running = True
            log.info(
                "Watcher scheduler started with %s minutes interval (max_jobs=%s)",
                self.settings.scheduler_interval_minutes,
                self.settings.scheduler_max_jobs_per_run,
            )

    def stop(self) -> None:
        with self._lock:
            if self._scheduler is not None:
                try:
                    if self._scheduler.running:
                        self._scheduler.shutdown(wait=False)
                except Exception:
                    log.exception("Error shutting down scheduler")
                self._scheduler = None
            self._running = False

    def status(self) -> dict[str, Any]:
        jobs: list[dict[str, Any]] = []
        if self._scheduler is not None:
            for job in self._scheduler.get_jobs():
                jobs.append(
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": job.next_run_time.isoformat()
                        if job.next_run_time
                        else None,
                        "trigger": str(job.trigger),
                    }
                )
        return {
            "enabled": self.settings.scheduler_enabled,
            "running": self.is_running,
            "interval_minutes": self.settings.scheduler_interval_minutes,
            "max_jobs_per_run": self.settings.scheduler_max_jobs_per_run,
            "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
            "last_run_summary": self._last_run_summary,
            "recent_runs": self.recent_runs,
            "jobs": jobs,
        }

    def _extract_source_urls(self, watcher) -> list[str]:
        # Öncelik: metadata.source_urls (eski API ile uyumluluk)
        meta = watcher.metadata or {}
        source_urls = meta.get("source_urls", []) if isinstance(meta, dict) else []
        # Fallback #1: search_criteria JSON kolonu (yeni watcher kayıtlarında buraya yazılıyor)
        if not source_urls:
            sc = getattr(watcher, "search_criteria", None) or {}
            if isinstance(sc, dict):
                source_urls = sc.get("source_urls", []) or sc.get("sources", []) or []
            elif isinstance(sc, str):
                try:
                    import json as _j

                    sc_d = _j.loads(sc)
                    source_urls = (
                        sc_d.get("source_urls", []) or sc_d.get("sources", []) or []
                    )
                except Exception:
                    logging.warning("Scheduler watcher source config JSON parse edilemedi, boş kaynak kullanıldı")
                    source_urls = []
        # Her ikisi de list değilse boş
        if not isinstance(source_urls, list):
            return []
        return [str(item).strip() for item in source_urls if str(item).strip()]


watcher_scheduler = WatcherScheduler()
