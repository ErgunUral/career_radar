from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .schemas import (
    ArchiveRecord,
    NotificationRecord,
    OperationLogRecord,
    SyncRunRecord,
    WatcherRecord,
)


class InMemoryWatcherRepository:
    def __init__(self) -> None:
        self.watchers: dict[str, WatcherRecord] = {}
        self.runs: dict[str, list[SyncRunRecord]] = defaultdict(list)
        self.archive: dict[tuple[str, str], ArchiveRecord] = {}
        self.notifications: list[NotificationRecord] = []
        self._logs: list[OperationLogRecord] = []
        self._log_id_seq: int = 1

    def list_watchers(self) -> list[WatcherRecord]:
        return sorted(
            self.watchers.values(), key=lambda watcher: watcher.created_at, reverse=True
        )

    def save_watcher(self, watcher: WatcherRecord) -> WatcherRecord:
        self.watchers[watcher.id] = watcher
        return watcher

    def get_watcher(self, watcher_id: str) -> WatcherRecord:
        return self.watchers[watcher_id]

    def delete_watcher(self, watcher_id: str) -> bool:
        if watcher_id in self.watchers:
            del self.watchers[watcher_id]
            return True
        return False

    def add_run(self, run: SyncRunRecord) -> SyncRunRecord:
        self.runs[run.watcher_id].append(run)
        return run

    def list_runs(self, watcher_id: str) -> list[SyncRunRecord]:
        return list(self.runs.get(watcher_id, []))

    def save_archive(self, record: ArchiveRecord) -> ArchiveRecord:
        self.archive[(record.user_id, record.job_id)] = record
        return record

    def get_archive(self, user_id: str, job_id: str) -> ArchiveRecord | None:
        return self.archive.get((user_id, job_id))

    def list_archive(self, user_id: str | None = None) -> list[ArchiveRecord]:
        items: list[ArchiveRecord] = list(self.archive.values())
        if user_id:
            items = [item for item in items if item.user_id == user_id]
        return sorted(items, key=lambda item: item.last_seen_at, reverse=True)

    def add_notification(self, notification: NotificationRecord) -> NotificationRecord:
        self.notifications.append(notification)
        return notification

    def save_notification(self, notification: NotificationRecord) -> NotificationRecord:
        for idx, item in enumerate(self.notifications):
            if item.id == notification.id:
                self.notifications[idx] = notification
                return notification
        self.notifications.append(notification)
        return notification

    def get_notification(self, notification_id: str) -> NotificationRecord | None:
        for item in self.notifications:
            if item.id == notification_id:
                return item
        return None

    def update_notification_is_read(
        self, notification_id: str, is_read: bool = True
    ) -> NotificationRecord | None:
        item = self.get_notification(notification_id)
        if not item:
            return None
        updated = item.model_copy(update={"is_read": is_read})
        self.save_notification(updated)
        return updated

    def mark_all_notifications_read(self, user_id: str) -> int:
        count = 0
        for idx, item in enumerate(self.notifications):
            if item.user_id == user_id and not item.is_read:
                self.notifications[idx] = item.model_copy(update={"is_read": True})
                count += 1
        return count

    def list_notifications(
        self, user_id: str | None = None
    ) -> list[NotificationRecord]:
        items = self.notifications
        if user_id:
            items = [item for item in items if item.user_id == user_id]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def log_event(
        self,
        *,
        level: str,
        source: str,
        message: str,
        user_id: str | None = None,
        watcher_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> OperationLogRecord:
        ts = timestamp or datetime.now(timezone.utc)
        # timezone-aware olmasını garanti et (karşılaştırma için)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rec = OperationLogRecord(
            id=self._log_id_seq,
            timestamp=ts,
            level=str(level or "INFO").upper(),
            source=source or "api",
            user_id=user_id,
            watcher_id=watcher_id,
            message=message,
            metadata=metadata or {},
        )
        self._log_id_seq += 1
        self._logs.append(rec)
        return rec

    def list_logs(
        self,
        *,
        level: str | None = None,
        source: str | None = None,
        user_id: str | None = None,
        watcher_id: str | None = None,
        limit: int = 100,
    ) -> list[OperationLogRecord]:
        items = self._logs
        if level:
            lv = str(level).upper()
            items = [x for x in items if str(x.level).upper() == lv]
        if source:
            items = [x for x in items if str(x.source) == str(source)]
        if user_id:
            items = [x for x in items if (x.user_id == user_id or x.user_id is None)]
        if watcher_id:
            items = [x for x in items if x.watcher_id == watcher_id]

        # safe sort — naive tz varsa UTC olarak ele al
        def _sort_key(x: OperationLogRecord) -> datetime:
            ts = x.timestamp
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts

        out = sorted(items, key=_sort_key, reverse=True)
        return out[: max(1, int(limit or 1))]

    def get_job_notifications(
        self, user_id: str, job_id: str
    ) -> list[NotificationRecord]:
        return [
            notification
            for notification in self.notifications
            if notification.user_id == user_id and notification.job_id == job_id
        ]


repository = InMemoryWatcherRepository()
