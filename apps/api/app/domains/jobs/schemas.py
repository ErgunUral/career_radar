from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ..matching.schemas import JobPostingInput, MatchResult, WorkMode


class JobSourcePlatform(str, Enum):
    linkedin = "linkedin"
    kariyernet = "kariyernet"
    indeed = "indeed"
    eleman_net = "eleman_net"
    secrethr = "secrethr"
    yenibiris = "yenibiris"
    jobturk = "jobturk"
    company_page = "company_page"
    manual_import = "manual_import"
    email_alert = "email_alert"


class JobImportRequest(BaseModel):
    user_id: str
    profile_id: str | None = None
    title: str
    company_name: str
    source_platform: JobSourcePlatform = JobSourcePlatform.manual_import
    source_url: str | None = None
    location: str = ""
    work_mode: WorkMode | None = None
    language: str = "Türkçe"
    raw_text: str
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobAnalysisRequest(BaseModel):
    profile_id: str


class JobRecord(BaseModel):
    id: str
    user_id: str
    profile_id: str | None = None
    title: str
    company_name: str
    source_platform: JobSourcePlatform
    source_url: str | None = None
    location: str = ""
    work_mode: WorkMode = WorkMode.hybrid
    language: str = "Türkçe"
    raw_text: str
    parsed_job: JobPostingInput
    analysis_result: MatchResult | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobDetailResponse(BaseModel):
    job: JobRecord


class ApplicationStatus(str, Enum):
    discovered = "Keşfedildi"
    review = "İncelenecek"
    apply = "Başvurulacak"
    applied = "Başvuruldu"
    hr_interview = "İnsan kaynakları görüşmesi"
    technical_interview = "Teknik görüşme"
    manager_interview = "Yönetici görüşmesi"
    offer_waiting = "Teklif bekleniyor"
    offer_received = "Teklif alındı"
    rejected = "Reddedildi"
    withdrawn = "Kullanıcı tarafından vazgeçildi"


class ApplicationCreateRequest(BaseModel):
    user_id: str
    job_id: str
    status: ApplicationStatus = ApplicationStatus.discovered
    notes: str = ""
    contact_person: str = ""
    expected_salary: float | None = Field(default=None, ge=0)
    offered_salary: float | None = Field(default=None, ge=0)
    reminder_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationUpdateRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None
    contact_person: str | None = None
    expected_salary: float | None = Field(default=None, ge=0)
    offered_salary: float | None = Field(default=None, ge=0)
    reminder_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ApplicationRecord(BaseModel):
    id: str
    user_id: str
    job_id: str
    status: ApplicationStatus
    notes: str = ""
    contact_person: str = ""
    expected_salary: float | None = None
    offered_salary: float | None = None
    reminder_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
