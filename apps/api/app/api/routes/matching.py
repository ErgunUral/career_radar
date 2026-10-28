from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ...core.auth import verify_api_key
from ...core.config import Settings, get_settings
from ...domains.matching.schemas import (
    MatchRequest,
    MatchResponse,
    PreprocessRequest,
    PreprocessResponse,
)
from ...domains.matching.service import HybridMatchingService

router = APIRouter(prefix="/api/v1/matching", tags=["matching"])


def get_service(settings: Settings = Depends(get_settings)) -> HybridMatchingService:
    return HybridMatchingService(settings=settings)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/preprocess", response_model=PreprocessResponse)
def preprocess_payload(
    payload: PreprocessRequest,
    service: HybridMatchingService = Depends(get_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> PreprocessResponse:
    return service.preprocess_samples(payload)


@router.post("/batch-match", response_model=MatchResponse)
def batch_match(
    payload: MatchRequest,
    service: HybridMatchingService = Depends(get_service),
    _auth: Annotated[bool, Depends(verify_api_key)] = True,
) -> MatchResponse:
    return service.match_jobs(payload)
