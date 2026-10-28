from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ...core.auth import verify_api_key
from ...core.scheduler import watcher_scheduler

scheduler_router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


@scheduler_router.get("/status")
def get_scheduler_status() -> dict:
    return watcher_scheduler.status()


@scheduler_router.post("/start")
def start_scheduler(
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> dict:
    if watcher_scheduler.is_running:
        return {"status": "already_running", **watcher_scheduler.status()}
    try:
        watcher_scheduler.start()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Scheduler başlatılamadı: {exc}"
        ) from exc
    return {"status": "started", **watcher_scheduler.status()}


@scheduler_router.post("/stop")
def stop_scheduler(
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> dict:
    if not watcher_scheduler.is_running:
        return {"status": "already_stopped", **watcher_scheduler.status()}
    watcher_scheduler.stop()
    return {"status": "stopped", **watcher_scheduler.status()}


@scheduler_router.post("/run")
def run_all_watchers_now(
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> dict:
    try:
        summary = watcher_scheduler.run_all_active_watchers()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Watcher çalıştırma başarısız: {exc}"
        ) from exc
    return {"status": "completed", "summary": summary}


@scheduler_router.post("/run/{watcher_id}")
def run_single_watcher_now(
    watcher_id: str,
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> dict:
    try:
        result = watcher_scheduler.run_watcher(watcher_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Watcher bulunamadı.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Watcher çalıştırma başarısız: {exc}"
        ) from exc

    status_ok = result.get("status") == "completed"
    summary = {
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "duration_seconds": result.get("duration_seconds"),
        "trigger": result.get("trigger", "manual_single"),
        "watchers_scanned": 1,
        "watchers_with_urls": 1 if status_ok else 0,
        "watchers_dispatched": 1,
        "watchers_failed": 0 if status_ok else 1,
        "processed_jobs_total": int(result.get("processed_jobs") or 0),
        "matched_jobs_total": int(result.get("matched_jobs") or 0),
        "notifications_created_total": int(result.get("notifications_created") or 0),
        "inactive_jobs_skipped_total": int(result.get("inactive_jobs_skipped") or 0),
        "per_watcher": [
            {
                "watcher_id": result.get("watcher_id"),
                "status": result.get("status"),
                "processed_jobs": result.get("processed_jobs"),
                "matched_jobs": result.get("matched_jobs"),
                "notifications_created": result.get("notifications_created"),
                "inactive_jobs_skipped": result.get("inactive_jobs_skipped"),
                "source_reports": result.get("source_reports") or [],
                "error": result.get("error"),
            }
        ],
    }
    return {
        "status": "completed",
        "summary": summary,
        "result": {
            "watcher_id": result.get("watcher_id"),
            "status": result.get("status"),
            "processed_jobs": result.get("processed_jobs"),
            "matched_jobs": result.get("matched_jobs"),
            "notifications_created": result.get("notifications_created"),
            "inactive_jobs_skipped": result.get("inactive_jobs_skipped"),
            "started_at": result.get("started_at"),
            "finished_at": result.get("finished_at"),
            "duration_seconds": result.get("duration_seconds"),
            "trigger": result.get("trigger"),
            "source_reports": result.get("source_reports") or [],
            "error": result.get("error"),
        },
    }
