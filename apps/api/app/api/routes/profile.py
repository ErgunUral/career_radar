from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from ...core.auth import verify_api_key
from ...core.config import Settings, get_settings
from ...core.database import init_database
from ...domains.profile.parser import CvParser
from ...domains.profile.repository import profile_repository
from ...domains.profile.schemas import (
    CandidateProfileRecord,
    CvParseRequest,
    CvUploadResponse,
    ProfileUpdateRequest,
)
from ...domains.profile.service import ProfileService

router = APIRouter(tags=["profile"])


def get_profile_service(settings: Settings = Depends(get_settings)) -> ProfileService:
    init_database()
    return ProfileService(
        repository=profile_repository, parser=CvParser(), settings=settings
    )


@router.post("/api/v1/files/cv", response_model=CvUploadResponse)
async def upload_cv(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    language: str = Form(default="tr"),
    service: ProfileService = Depends(get_profile_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> CvUploadResponse:
    try:
        return CvUploadResponse(
            file=await service.upload_cv(file=file, user_id=user_id, language=language)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/cv/parse", response_model=CandidateProfileRecord)
def parse_cv(
    payload: CvParseRequest,
    service: ProfileService = Depends(get_profile_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> CandidateProfileRecord:
    try:
        return service.parse_cv(payload.file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="CV dosyası bulunamadı.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/v1/profile", response_model=CandidateProfileRecord)
def get_profile(
    profile_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    service: ProfileService = Depends(get_profile_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> CandidateProfileRecord:
    try:
        return service.get_profile(profile_id=profile_id, user_id=user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Profil bulunamadı.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/v1/profile/{profile_id}", response_model=CandidateProfileRecord)
def update_profile(
    profile_id: str,
    payload: ProfileUpdateRequest,
    service: ProfileService = Depends(get_profile_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> CandidateProfileRecord:
    try:
        return service.update_profile(profile_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Profil bulunamadı.") from exc
