from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select

from ...core.database import SessionLocal
from .models import (
    ArchiveModel,
    NotificationModel,
    OperationLogModel,
    SyncRunModel,
    WatcherModel,
)
from .schemas import (
    ArchiveRecord,
    NotificationRecord,
    OperationLogRecord,
    SyncRunRecord,
    WatcherRecord,
)


class SQLAlchemyWatcherRepository:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def list_watchers(self) -> list[WatcherRecord]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(WatcherModel).order_by(WatcherModel.created_at.desc())
            ).all()
            return [self._to_watcher(row) for row in rows]

    def save_watcher(self, watcher: WatcherRecord) -> WatcherRecord:
        with self.session_factory() as session:
            row = session.get(WatcherModel, watcher.id)
            data = watcher.model_dump(mode="json")
            if row is None:
                row = WatcherModel(
                    id=data["id"],
                    user_id=data["user_id"],
                    query_name=data["query_name"],
                    source_platform=data["source_platform"],
                    search_criteria=data["search_criteria"],
                    candidate_profile=data["candidate_profile"],
                    weights=data["weights"],
                    minimum_match_score=data["minimum_match_score"],
                    sync_frequency_minutes=data["sync_frequency_minutes"],
                    notification_channels=data["notification_channels"],
                    is_active=data["is_active"],
                    created_at=watcher.created_at,
                    updated_at=watcher.updated_at,
                    last_synced_at=watcher.last_synced_at,
                    metadata_json=data["metadata"],
                )
                session.add(row)
            else:
                row.user_id = data["user_id"]
                row.query_name = data["query_name"]
                row.source_platform = data["source_platform"]
                row.search_criteria = data["search_criteria"]
                row.candidate_profile = data["candidate_profile"]
                row.weights = data["weights"]
                row.minimum_match_score = data["minimum_match_score"]
                row.sync_frequency_minutes = data["sync_frequency_minutes"]
                row.notification_channels = data["notification_channels"]
                row.is_active = data["is_active"]
                row.updated_at = watcher.updated_at
                row.last_synced_at = watcher.last_synced_at
                row.metadata_json = data["metadata"]
            session.commit()
            return self._to_watcher(row)

    def get_watcher(self, watcher_id: str) -> WatcherRecord:
        with self.session_factory() as session:
            row = session.get(WatcherModel, watcher_id)
            if row is None:
                raise KeyError(watcher_id)
            return self._to_watcher(row)

    def delete_watcher(self, watcher_id: str) -> bool:
        with self.session_factory() as session:
            row = session.get(WatcherModel, watcher_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def add_run(self, run: SyncRunRecord) -> SyncRunRecord:
        with self.session_factory() as session:
            data = run.model_dump(mode="json")
            row = SyncRunModel(
                id=data["id"],
                watcher_id=data["watcher_id"],
                user_id=data["user_id"],
                status=data["status"],
                started_at=run.started_at,
                finished_at=run.finished_at,
                processed_jobs=data["processed_jobs"],
                matched_jobs=data["matched_jobs"],
                notifications_created=data["notifications_created"],
                error_message=data["error_message"],
                metadata_json=data["metadata"],
            )
            session.add(row)
            session.commit()
            return self._to_run(row)

    def update_run(self, run: SyncRunRecord) -> SyncRunRecord:
        with self.session_factory() as session:
            row = session.get(SyncRunModel, run.id)
            if row is None:
                raise KeyError(run.id)
            data = run.model_dump(mode="json")
            row.status = data["status"]
            row.finished_at = run.finished_at
            row.processed_jobs = data["processed_jobs"]
            row.matched_jobs = data["matched_jobs"]
            row.notifications_created = data["notifications_created"]
            row.error_message = data["error_message"]
            row.metadata_json = data["metadata"]
            session.commit()
            return self._to_run(row)

    def list_runs(self, watcher_id: str) -> list[SyncRunRecord]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(SyncRunModel)
                .where(SyncRunModel.watcher_id == watcher_id)
                .order_by(SyncRunModel.started_at.desc())
            ).all()
            return [self._to_run(row) for row in rows]

    def save_archive(self, record: ArchiveRecord) -> ArchiveRecord:
        with self.session_factory() as session:
            row = session.scalar(
                select(ArchiveModel).where(
                    ArchiveModel.user_id == record.user_id,
                    ArchiveModel.job_id == record.job_id,
                )
            )
            data = record.model_dump(mode="json")
            if row is None:
                row = ArchiveModel(
                    user_id=data["user_id"],
                    watcher_id=data["watcher_id"],
                    job_id=data["job_id"],
                    title=data["title"],
                    company_name=data["company_name"],
                    location=data["location"],
                    source_platform=data["source_platform"],
                    first_seen_at=record.first_seen_at,
                    last_seen_at=record.last_seen_at,
                    notification_sent=data["notification_sent"],
                    notifications_sent=data["notifications_sent"],
                    last_match_score=data["last_match_score"],
                    last_recommendation=data["last_recommendation"],
                    metadata_json=data["metadata"],
                )
                session.add(row)
            else:
                row.watcher_id = data["watcher_id"]
                row.title = data["title"]
                row.company_name = data["company_name"]
                row.location = data["location"]
                row.source_platform = data["source_platform"]
                row.last_seen_at = record.last_seen_at
                row.notification_sent = data["notification_sent"]
                row.notifications_sent = data["notifications_sent"]
                row.last_match_score = data["last_match_score"]
                row.last_recommendation = data["last_recommendation"]
                row.metadata_json = data["metadata"]
            session.commit()
            return self._to_archive(row)

    def get_archive(self, user_id: str, job_id: str) -> ArchiveRecord | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(ArchiveModel).where(
                    ArchiveModel.user_id == user_id, ArchiveModel.job_id == job_id
                )
            )
            return self._to_archive(row) if row else None

    def list_archive(self, user_id: str | None = None) -> list[ArchiveRecord]:
        with self.session_factory() as session:
            query = select(ArchiveModel).order_by(ArchiveModel.last_seen_at.desc())
            if user_id:
                query = query.where(ArchiveModel.user_id == user_id)
            rows = session.scalars(query).all()
            return [self._to_archive(row) for row in rows]

    def add_notification(self, notification: NotificationRecord) -> NotificationRecord:
        with self.session_factory() as session:
            data = notification.model_dump(mode="json")
            row = NotificationModel(
                id=data["id"],
                user_id=data["user_id"],
                watcher_id=data["watcher_id"],
                job_id=data["job_id"],
                channel=data["channel"],
                title=data["title"],
                message=data["message"],
                created_at=notification.created_at,
                is_read=data["is_read"],
                metadata_json=data["metadata"],
            )
            session.add(row)
            session.commit()
            return self._to_notification(row)

    def save_notification(self, notification: NotificationRecord) -> NotificationRecord:
        with self.session_factory() as session:
            row = session.get(NotificationModel, notification.id)
            data = notification.model_dump(mode="json")
            if row is None:
                row = NotificationModel(
                    id=data["id"],
                    user_id=data["user_id"],
                    watcher_id=data["watcher_id"],
                    job_id=data["job_id"],
                    channel=data["channel"],
                    title=data["title"],
                    message=data["message"],
                    created_at=notification.created_at,
                    is_read=data["is_read"],
                    metadata_json=data["metadata"],
                )
                session.add(row)
            else:
                row.user_id = data["user_id"]
                row.watcher_id = data["watcher_id"]
                row.job_id = data["job_id"]
                row.channel = data["channel"]
                row.title = data["title"]
                row.message = data["message"]
                row.is_read = bool(data.get("is_read", False))
                row.metadata_json = data.get("metadata") or {}
            session.commit()
            return self._to_notification(row)

    def get_notification(self, notification_id: str) -> NotificationRecord | None:
        with self.session_factory() as session:
            row = session.get(NotificationModel, notification_id)
            return self._to_notification(row) if row else None

    def update_notification_is_read(
        self, notification_id: str, is_read: bool = True
    ) -> NotificationRecord | None:
        with self.session_factory() as session:
            row = session.get(NotificationModel, notification_id)
            if row is None:
                return None
            row.is_read = bool(is_read)
            session.commit()
            return self._to_notification(row)

    def mark_all_notifications_read(self, user_id: str) -> int:
        with self.session_factory() as session:
            from sqlalchemy import update

            stmt = (
                update(NotificationModel)
                .where(
                    NotificationModel.user_id == user_id,
                    NotificationModel.is_read.is_(False),
                )
                .values(is_read=True)
            )
            result = session.execute(stmt)
            session.commit()
            return int(result.rowcount or 0)

    def list_notifications(
        self, user_id: str | None = None
    ) -> list[NotificationRecord]:
        with self.session_factory() as session:
            query = select(NotificationModel).order_by(
                NotificationModel.created_at.desc()
            )
            if user_id:
                query = query.where(NotificationModel.user_id == user_id)
            rows = session.scalars(query).all()
            return [self._to_notification(row) for row in rows]

    def get_job_notifications(
        self, user_id: str, job_id: str
    ) -> list[NotificationRecord]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(NotificationModel).where(
                    NotificationModel.user_id == user_id,
                    NotificationModel.job_id == job_id,
                )
            ).all()
            return [self._to_notification(row) for row in rows]

    def clear_all(self) -> None:
        with self.session_factory() as session:
            session.execute(delete(NotificationModel))
            session.execute(delete(ArchiveModel))
            session.execute(delete(SyncRunModel))
            session.execute(delete(WatcherModel))
            session.commit()

    def _to_watcher(self, row: WatcherModel) -> WatcherRecord:
        return WatcherRecord.model_validate(
            {
                "id": row.id,
                "user_id": row.user_id,
                "query_name": row.query_name,
                "source_platform": row.source_platform,
                "search_criteria": row.search_criteria,
                "candidate_profile": row.candidate_profile,
                "weights": row.weights,
                "minimum_match_score": row.minimum_match_score,
                "sync_frequency_minutes": row.sync_frequency_minutes,
                "notification_channels": row.notification_channels,
                "is_active": row.is_active,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "last_synced_at": row.last_synced_at,
                "metadata": row.metadata_json or {},
            }
        )

    def _to_run(self, row: SyncRunModel) -> SyncRunRecord:
        return SyncRunRecord.model_validate(
            {
                "id": row.id,
                "watcher_id": row.watcher_id,
                "user_id": row.user_id,
                "status": row.status,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "processed_jobs": row.processed_jobs,
                "matched_jobs": row.matched_jobs,
                "notifications_created": row.notifications_created,
                "error_message": row.error_message,
                "metadata": row.metadata_json or {},
            }
        )

    def _to_archive(self, row: ArchiveModel) -> ArchiveRecord:
        metadata = row.metadata_json or {}
        return ArchiveRecord.model_validate(
            {
                "user_id": row.user_id,
                "watcher_id": row.watcher_id,
                "job_id": row.job_id,
                "title": row.title,
                "company_name": row.company_name,
                "location": row.location,
                "source_platform": row.source_platform,
                "source_url": metadata.get("source_url"),
                "apply_url": metadata.get("apply_url"),
                "first_seen_at": row.first_seen_at,
                "last_seen_at": row.last_seen_at,
                "notification_sent": row.notification_sent,
                "notifications_sent": row.notifications_sent,
                "last_match_score": row.last_match_score,
                "last_recommendation": row.last_recommendation,
                "metadata": metadata,
            }
        )

    def _to_notification(self, row: NotificationModel) -> NotificationRecord:
        return NotificationRecord.model_validate(
            {
                "id": row.id,
                "user_id": row.user_id,
                "watcher_id": row.watcher_id,
                "job_id": row.job_id,
                "channel": row.channel,
                "title": row.title,
                "message": row.message,
                "created_at": row.created_at,
                "is_read": row.is_read,
                "metadata": row.metadata_json or {},
            }
        )

    def _to_log(self, row: OperationLogModel) -> OperationLogRecord:
        return OperationLogRecord.model_validate(
            {
                "id": row.id,
                "timestamp": row.timestamp,
                "level": row.level,
                "source": row.source,
                "user_id": row.user_id,
                "watcher_id": row.watcher_id,
                "message": row.message,
                "metadata": row.metadata_json or {},
            }
        )

    def log_event(
        self,
        *,
        level: str,
        source: str,
        message: str,
        user_id: str | None = None,
        watcher_id: str | None = None,
        metadata: dict | None = None,
        timestamp: datetime | None = None,
    ) -> OperationLogRecord:
        from .service import utcnow

        ts = timestamp or utcnow()
        with self.session_factory() as session:
            row = OperationLogModel(
                timestamp=ts,
                level=str(level or "INFO").upper(),
                source=source or "api",
                user_id=user_id,
                watcher_id=watcher_id,
                message=message,
                metadata_json=metadata or {},
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_log(row)

    def list_logs(
        self,
        *,
        level: str | None = None,
        source: str | None = None,
        user_id: str | None = None,
        watcher_id: str | None = None,
        limit: int = 100,
    ) -> list[OperationLogRecord]:
        from sqlalchemy import desc as _desc

        with self.session_factory() as session:
            stmt = select(OperationLogModel)
            if level:
                stmt = stmt.where(OperationLogModel.level == str(level).upper())
            if source:
                stmt = stmt.where(OperationLogModel.source == str(source))
            if user_id:
                stmt = stmt.where(
                    (OperationLogModel.user_id == user_id)
                    | (OperationLogModel.user_id.is_(None))
                )
            if watcher_id:
                stmt = stmt.where(OperationLogModel.watcher_id == watcher_id)
            stmt = stmt.order_by(_desc(OperationLogModel.timestamp)).limit(
                max(1, int(limit or 1))
            )
            rows = session.scalars(stmt).all()
            return [self._to_log(r) for r in rows]


db_repository = SQLAlchemyWatcherRepository()
