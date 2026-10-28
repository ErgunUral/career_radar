from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ..matching.schemas import CandidateProfileInput


class CvParseStatus(str, Enum):
    uploaded = "uploaded"
    parsed = "parsed"
    failed = "failed"


class CvFileRecord(BaseModel):
    id: str
    user_id: str
    filename: str
    content_type: str
    storage_path: str
    language: str = "tr"
    parse_status: CvParseStatus
    extracted_text: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class CvUploadResponse(BaseModel):
    file: CvFileRecord


class CvParseRequest(BaseModel):
    file_id: str


class CandidateProfileRecord(BaseModel):
    id: str
    user_id: str
    cv_file_id: str | None = None
    profile: CandidateProfileInput
    professional_summary: str
    target_positions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfileUpdateRequest(BaseModel):
    headline: str | None = None
    summary: str | None = None
    total_experience_years: float | None = Field(default=None, ge=0, le=60)
    management_years: float | None = Field(default=None, ge=0, le=60)
    team_size_managed: int | None = Field(default=None, ge=0, le=100000)
    skills: list[str] | None = None
    industries: list[str] | None = None
    languages: list[str] | None = None
    certifications: list[str] | None = None
    educations: list[str] | None = None
    preferred_locations: list[str] | None = None
    work_modes: list[str] | None = None
    salary_expectation: float | None = None
    metadata: dict[str, Any] | None = None
