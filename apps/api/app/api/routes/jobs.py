from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.auth import verify_api_key
from ...core.config import Settings, get_settings
from ...core.database import init_database
from ...domains.jobs.parser import JobParser
from ...domains.jobs.repository import jobs_repository
from ...domains.jobs.schemas import (
    ApplicationCreateRequest,
    ApplicationRecord,
    ApplicationUpdateRequest,
    JobAnalysisRequest,
    JobDetailResponse,
    JobImportRequest,
    JobRecord,
)
from ...domains.jobs.service import JobsService
from ...domains.matching.service import HybridMatchingService
from ...domains.profile.repository import profile_repository

jobs_router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])
applications_router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


def get_jobs_service(settings: Settings = Depends(get_settings)) -> JobsService:
    init_database()
    return JobsService(
        repository=jobs_repository,
        profile_repository=profile_repository,
        matching_service=HybridMatchingService(settings=settings),
        parser=JobParser(),
    )


@jobs_router.get("", response_model=list[JobRecord])
def list_jobs(
    user_id: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    published_within_days: int | None = Query(default=None, ge=1, le=365),
    source_platform: list[str] | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="published_at"),
    sort_order: str = Query(default="desc"),
    dedupe: bool = Query(default=False),
    service: JobsService = Depends(get_jobs_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> list[JobRecord]:
    return service.list_jobs(
        user_id=user_id,
        active_only=active_only,
        published_within_days=published_within_days,
        source_platforms=source_platform,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        dedupe=dedupe,
    )


@jobs_router.post("/import", response_model=JobRecord)
def import_job(
    payload: JobImportRequest,
    service: JobsService = Depends(get_jobs_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> JobRecord:
    try:
        return service.import_job(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Profil bulunamadı.") from exc


@jobs_router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(
    job_id: str,
    service: JobsService = Depends(get_jobs_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> JobDetailResponse:
    try:
        return service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.") from exc


@jobs_router.post("/{job_id}/analyze", response_model=JobDetailResponse)
def analyze_job(
    job_id: str,
    payload: JobAnalysisRequest,
    service: JobsService = Depends(get_jobs_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> JobDetailResponse:
    try:
        return service.analyze_job(job_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="İlan veya profil bulunamadı."
        ) from exc


@applications_router.get("", response_model=list[ApplicationRecord])
def list_applications(
    user_id: str | None = Query(default=None),
    service: JobsService = Depends(get_jobs_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> list[ApplicationRecord]:
    return service.list_applications(user_id=user_id)


@applications_router.post("", response_model=ApplicationRecord)
def create_application(
    payload: ApplicationCreateRequest,
    service: JobsService = Depends(get_jobs_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> ApplicationRecord:
    try:
        return service.create_application(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@applications_router.patch("/{application_id}", response_model=ApplicationRecord)
def update_application(
    application_id: str,
    payload: ApplicationUpdateRequest,
    service: JobsService = Depends(get_jobs_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> ApplicationRecord:
    try:
        return service.update_application(application_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Başvuru bulunamadı.") from exc
