from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...core.database import Base


class WatcherModel(Base):
    __tablename__ = "watchers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    query_name: Mapped[str] = mapped_column(String(255), index=True)
    source_platform: Mapped[str] = mapped_column(String(64), index=True)
    search_criteria: Mapped[dict] = mapped_column(JSON)
    candidate_profile: Mapped[dict] = mapped_column(JSON)
    weights: Mapped[dict] = mapped_column(JSON)
    minimum_match_score: Mapped[float] = mapped_column(Float)
    sync_frequency_minutes: Mapped[int] = mapped_column(Integer)
    notification_channels: Mapped[list] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class SyncRunModel(Base):
    __tablename__ = "watcher_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    watcher_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    matched_jobs: Mapped[int] = mapped_column(Integer, default=0)
    notifications_created: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class ArchiveModel(Base):
    __tablename__ = "job_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    watcher_id: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255))
    source_platform: Mapped[str] = mapped_column(String(64), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    notifications_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_match_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_recommendation: Mapped[str] = mapped_column(String(128), default="")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    watcher_id: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class OperationLogModel(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    level: Mapped[str] = mapped_column(
        String(16), index=True
    )  # DEBUG / INFO / WARN / ERROR
    source: Mapped[str] = mapped_column(
        String(64), index=True
    )  # discovery / scheduler / email / api / match
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    watcher_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
