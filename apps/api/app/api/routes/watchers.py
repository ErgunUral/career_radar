from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.auth import verify_api_key
from ...core.config import Settings, get_settings
from ...core.database import init_database
from ...domains.jobs.parser import JobParser
from ...domains.jobs.repository import jobs_repository
from ...domains.jobs.service import JobsService
from ...domains.matching.service import HybridMatchingService
from ...domains.profile.repository import profile_repository
from ...domains.watchers.db_repository import db_repository
from ...domains.watchers.discovery import LiveJobDiscoveryService
from ...domains.watchers.schemas import (
    ArchiveJobDetailResponse,
    ArchiveRecord,
    LogCreateRequest,
    NotificationRecord,
    OperationLogRecord,
    SyncRunRecord,
    WatcherCreateRequest,
    WatcherDiscoverRequest,
    WatcherDiscoverResponse,
    WatcherRecord,
    WatcherRunRequest,
    WatcherRunResponse,
    WatcherUpdateRequest,
)
from ...domains.watchers.service import WatcherService

watchers_router = APIRouter(prefix="/api/v1/watchers", tags=["watchers"])
archive_router = APIRouter(prefix="/api/v1/archive/jobs", tags=["archive"])
notifications_router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
logs_router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


def get_watcher_service(settings: Settings = Depends(get_settings)) -> WatcherService:
    init_database()
    matching_service = HybridMatchingService(settings=settings)
    jobs_service = JobsService(
        repository=jobs_repository,
        profile_repository=profile_repository,
        matching_service=matching_service,
        parser=JobParser(),
    )
    return WatcherService(
        repository=db_repository,
        matching_service=matching_service,
        settings=settings,
        profile_repository=profile_repository,
        jobs_service=jobs_service,
        discovery_service=LiveJobDiscoveryService(),
    )


@watchers_router.get("", response_model=list[WatcherRecord])
def list_watchers(
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> list[WatcherRecord]:
    return service.list_watchers()


@watchers_router.post("", response_model=WatcherRecord)
def create_watcher(
    payload: WatcherCreateRequest,
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> WatcherRecord:
    try:
        return service.create_watcher(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Profil bulunamadı.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@watchers_router.patch("/{watcher_id}", response_model=WatcherRecord)
def update_watcher(
    watcher_id: str,
    payload: WatcherUpdateRequest,
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> WatcherRecord:
    try:
        return service.update_watcher(watcher_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Watcher bulunamadı.") from exc


@watchers_router.patch("/{watcher_id}/active", response_model=WatcherRecord)
def toggle_watcher_active(
    watcher_id: str,
    is_active: bool = True,
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> WatcherRecord:
    try:
        return service.toggle_watcher_active(watcher_id, is_active)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Watcher bulunamadı.") from exc


@watchers_router.delete("/{watcher_id}", response_model=dict)
def delete_watcher(
    watcher_id: str,
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> dict:
    ok = service.delete_watcher(watcher_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Watcher bulunamadı.")
    return {"ok": True, "deleted_watcher_id": watcher_id}


@watchers_router.post("/{watcher_id}/run", response_model=WatcherRunResponse)
def run_watcher(
    watcher_id: str,
    payload: WatcherRunRequest,
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> WatcherRunResponse:
    try:
        return service.run_watcher(watcher_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Watcher bulunamadı.") from exc


@watchers_router.post("/{watcher_id}/discover", response_model=WatcherDiscoverResponse)
def discover_watcher(
    watcher_id: str,
    payload: WatcherDiscoverRequest,
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> WatcherDiscoverResponse:
    try:
        return service.discover_jobs(watcher_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Watcher bulunamadı.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@watchers_router.get("/{watcher_id}/runs", response_model=list[SyncRunRecord])
def list_runs(
    watcher_id: str,
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> list[SyncRunRecord]:
    return service.list_runs(watcher_id)


@archive_router.get("", response_model=list[ArchiveRecord])
def list_archive(
    user_id: str | None = Query(default=None),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> list[ArchiveRecord]:
    return service.list_archive(user_id=user_id)


@archive_router.get("/{job_id}", response_model=ArchiveJobDetailResponse)
def archive_detail(
    job_id: str,
    user_id: str = Query(default="default-user"),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> ArchiveJobDetailResponse:
    try:
        return service.get_archive_detail(user_id=user_id, job_id=job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Arşiv kaydı bulunamadı.") from exc


@notifications_router.get("", response_model=list[NotificationRecord])
def list_notifications(
    user_id: str | None = Query(default=None),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> list[NotificationRecord]:
    return service.list_notifications(user_id=user_id)


# ── DİKKAT: Sabit path'ler {param} path'ten ÖNCE TANIMLANMALI (FastAPI sıra önemli!) ──
@notifications_router.get("/unread-count", response_model=dict)
def get_unread_notifications_count(
    user_id: str = Query(default="default-user"),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> dict:
    notifs = service.list_notifications(user_id=user_id) or []
    count = sum(1 for n in notifs if not getattr(n, "is_read", False))
    return {"ok": True, "unread_count": count, "user_id": user_id}


@notifications_router.patch("/read-all", response_model=dict)
def mark_all_notifications_read(
    user_id: str = Query(default="default-user"),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> dict:
    count = service.mark_all_notifications_read(user_id)
    return {"ok": True, "marked_read_count": count, "user_id": user_id}


@notifications_router.get("/{notification_id}", response_model=NotificationRecord)
def get_notification(
    notification_id: str,
    user_id: str | None = Query(default=None),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> NotificationRecord:
    item = service.get_notification(notification_id, user_id=user_id)
    if not item:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı.")
    return item


@notifications_router.patch(
    "/{notification_id}/read", response_model=NotificationRecord
)
def mark_notification_read(
    notification_id: str,
    user_id: str = Query(default="default-user"),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> NotificationRecord:
    item = service.mark_notification_read(
        notification_id, user_id=user_id, is_read=True
    )
    if not item:
        raise HTTPException(
            status_code=404, detail="Bildirim bulunamadı veya kullanıcıya ait değil."
        )
    return item


@notifications_router.patch(
    "/{notification_id}/unread", response_model=NotificationRecord
)
def mark_notification_unread(
    notification_id: str,
    user_id: str = Query(default="default-user"),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> NotificationRecord:
    item = service.mark_notification_read(
        notification_id, user_id=user_id, is_read=False
    )
    if not item:
        raise HTTPException(
            status_code=404, detail="Bildirim bulunamadı veya kullanıcıya ait değil."
        )
    return item


# ============================================================
# LOGS ROUTER · Operation Logs (discovery / scheduler / email / api)
# ============================================================
@logs_router.get("", response_model=list[OperationLogRecord])
def list_logs(
    level: str | None = Query(default=None, description="DEBUG / INFO / WARN / ERROR"),
    source: str | None = Query(
        default=None, description="discovery / scheduler / email / api / match"
    ),
    user_id: str | None = Query(default=None),
    watcher_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> list[OperationLogRecord]:
    return service.list_logs(
        level=level, source=source, user_id=user_id, watcher_id=watcher_id, limit=limit
    )


@logs_router.post("", response_model=OperationLogRecord)
def create_log(
    payload: LogCreateRequest,
    service: WatcherService = Depends(get_watcher_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> OperationLogRecord:
    try:
        return service.log_event(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
