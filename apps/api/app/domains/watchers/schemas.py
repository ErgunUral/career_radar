from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ..jobs.schemas import JobRecord, JobSourcePlatform
from ..matching.schemas import (
    CandidateProfileInput,
    JobPostingInput,
    MatchingWeights,
    WorkMode,
)


class SourcePlatform(str, Enum):
    linkedin_alert = "linkedin_alert"
    linkedin_search_url = "linkedin_search_url"
    email_forward = "email_forward"
    manual_import = "manual_import"


class SyncStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class OperationLogRecord(BaseModel):
    id: int
    timestamp: datetime
    level: LogLevel | str
    source: str
    user_id: str | None = None
    watcher_id: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LogCreateRequest(BaseModel):
    level: LogLevel | str = LogLevel.INFO
    source: str = "api"
    user_id: str | None = None
    watcher_id: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationChannel(str, Enum):
    in_app = "in_app"
    email = "email"


class SearchCriteria(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    work_modes: list[WorkMode] = Field(default_factory=list)
    min_experience_years: float | None = Field(default=None, ge=0, le=60)
    max_experience_years: float | None = Field(default=None, ge=0, le=60)
    position_types: list[str] = Field(default_factory=list)


class WatcherCreateRequest(BaseModel):
    user_id: str = "default-user"
    query_name: str
    source_platform: SourcePlatform
    search_criteria: SearchCriteria
    candidate_profile: CandidateProfileInput | None = None
    profile_id: str | None = None
    weights: MatchingWeights = Field(default_factory=MatchingWeights)
    minimum_match_score: float = Field(default=70.0, ge=0, le=100)
    sync_frequency_minutes: int = Field(default=60, ge=15, le=1440)
    notification_channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.in_app]
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_profile_source(self) -> WatcherCreateRequest:
        if self.candidate_profile is None and self.profile_id is None:
            raise ValueError(
                "Watcher oluşturmak için candidate_profile veya profile_id verilmelidir."
            )
        return self


class WatcherUpdateRequest(BaseModel):
    query_name: str | None = None
    search_criteria: SearchCriteria | None = None
    minimum_match_score: float | None = Field(default=None, ge=0, le=100)
    sync_frequency_minutes: int | None = Field(default=None, ge=15, le=1440)
    notification_channels: list[NotificationChannel] | None = None
    is_active: bool | None = None


class WatcherRecord(BaseModel):
    id: str
    user_id: str
    query_name: str
    source_platform: SourcePlatform
    search_criteria: SearchCriteria
    candidate_profile: CandidateProfileInput
    weights: MatchingWeights
    minimum_match_score: float
    sync_frequency_minutes: int
    notification_channels: list[NotificationChannel]
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    last_synced_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WatcherRunRequest(BaseModel):
    jobs: list[JobPostingInput]
    triggered_by: str = "manual"


class WatcherDiscoverRequest(BaseModel):
    source_urls: list[str] = Field(default_factory=list)
    triggered_by: str = "live-discovery"
    max_jobs: int = Field(default=10, ge=1, le=50)


class DiscoverySourceReport(BaseModel):
    source_url: str
    source_platform: JobSourcePlatform | None = None
    fetched_jobs: int = 0
    status: str = "completed"
    search_performed: bool = True
    verification_note: str | None = None
    error_message: str | None = None


class DiscoveredJobInput(BaseModel):
    title: str
    company_name: str
    source_platform: JobSourcePlatform = JobSourcePlatform.company_page
    source_url: str
    location: str = ""
    work_mode: WorkMode = WorkMode.hybrid
    language: str = "Türkçe"
    raw_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationRecord(BaseModel):
    id: str
    user_id: str
    watcher_id: str
    job_id: str
    channel: NotificationChannel
    title: str
    message: str
    created_at: datetime
    is_read: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArchiveRecord(BaseModel):
    user_id: str
    watcher_id: str
    job_id: str
    title: str
    company_name: str
    location: str
    source_platform: str
    source_url: str | None = None
    apply_url: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    notification_sent: bool
    notifications_sent: int = 0
    last_match_score: float = 0.0
    last_recommendation: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncRunRecord(BaseModel):
    id: str
    watcher_id: str
    user_id: str
    status: SyncStatus
    started_at: datetime
    finished_at: datetime | None = None
    processed_jobs: int = 0
    matched_jobs: int = 0
    notifications_created: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WatcherRunResponse(BaseModel):
    watcher: WatcherRecord
    run: SyncRunRecord
    archived_jobs: list[ArchiveRecord]
    notifications: list[NotificationRecord]


class WatcherDiscoverResponse(BaseModel):
    watcher: WatcherRecord
    run: SyncRunRecord
    archived_jobs: list[ArchiveRecord]
    notifications: list[NotificationRecord]
    imported_jobs: list[JobRecord]
    source_reports: list[DiscoverySourceReport]


class ArchiveJobDetailResponse(BaseModel):
    archive: ArchiveRecord
    notifications: list[NotificationRecord]
