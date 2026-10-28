from __future__ import annotations

import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.crypto import decrypt_env_value
from app.domains.jobs.schemas import JobImportRequest
from app.domains.jobs.service import JobsService
from app.domains.matching.schemas import MatchRequest
from app.domains.matching.service import HybridMatchingService
from app.domains.profile.repository import SQLAlchemyProfileRepository
from app.domains.watchers.discovery import LiveJobDiscoveryService
from .schemas import (
    ArchiveJobDetailResponse,
    ArchiveRecord,
    DiscoveredJobInput,
    LogCreateRequest,
    NotificationChannel,
    NotificationRecord,
    OperationLogRecord,
    SearchCriteria,
    SourcePlatform,
    SyncRunRecord,
    SyncStatus,
    WatcherCreateRequest,
    WatcherDiscoverRequest,
    WatcherDiscoverResponse,
    WatcherRecord,
    WatcherRunRequest,
    WatcherRunResponse,
    WatcherUpdateRequest,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmailSenderService:
    """SMTP ile email bildirim gönder (opsiyonel). SMTP env değişkenleri yoksa SESSİZCE atlar.

    ENV (isteğe bağlı — hepsi tanımlıysa email gönderimi aktif olur):
      SMTP_HOST  = smtp.gmail.com (veya başka)
      SMTP_PORT  = 465 (SSL) veya 587 (STARTTLS)
      SMTP_USER  = gonderen@firma.com
      SMTP_PASS  = app-password / şifre
      SMTP_FROM  = Başlık görüntüsü (opsiyonel, SMTP_USER varsayılan)
    """

    def __init__(self) -> None:
        _settings = get_settings()
        enc_key = _settings.encryption_key
        self.host = decrypt_env_value(os.environ.get("SMTP_HOST", ""), enc_key)
        try:
            self.port = int(decrypt_env_value(os.environ.get("SMTP_PORT", "0"), enc_key) or 0)
        except ValueError:
            self.port = 0
        self.user = decrypt_env_value(os.environ.get("SMTP_USER", ""), enc_key)
        self.password = decrypt_env_value(os.environ.get("SMTP_PASS", ""), enc_key)
        self.sender = (
            decrypt_env_value(os.environ.get("SMTP_FROM", ""), enc_key)
            or self.user
            or "CareerRadar AI <noreply@careerradar.local>"
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.port and self.user and self.password)

    def send_match_notification(
        self,
        to_email: str,
        archive: ArchiveRecord,
        total_score: float,
    ) -> bool:
        """Yüksek eşleşen ilan için email gönder — başarısızlıkta Exception atmaz, False döner."""
        if not to_email or "@" not in to_email:
            return False
        if not self.is_configured:
            return False
        try:
            msg = EmailMessage()
            msg["Subject"] = (
                f"[CareerRadar] %{total_score:.1f} Eşleşme: {archive.title} @ {archive.company_name or 'Firma'}"
            )
            msg["From"] = self.sender
            msg["To"] = to_email
            body = f"""Merhaba,

Yeni bir high-match ilan bulundu 🎯:

  Başlık      : {archive.title}
  Şirket      : {archive.company_name or "Belirtilmemiş"}
  Konum       : {archive.location or "Belirtilmemiş"}
  Platform    : {archive.source_platform or "—"}
  Skor        : %{total_score:.2f}  (eşik ≥)
  Öneri       : {archive.last_recommendation or "—"}
  İlan Linki  : {archive.source_url or "—"}

Dashboard'dan detayları görüntüleyebilirsiniz:
  http://localhost:8501

İyi çalışmalar,
CareerRadar AI · Kişisel İş Radar Paneli
"""
            msg.set_content(body)
            ctx = ssl.create_default_context()
            if self.port == 465:
                with smtplib.SMTP_SSL(
                    self.host, self.port, context=ctx, timeout=20
                ) as smtp:
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                    smtp.ehlo()
                    try:
                        smtp.starttls(context=ctx)
                        smtp.ehlo()
                    except Exception:
                        logging.info("SMTP STARTTLS desteklenmiyor, düz SMTP ile devam ediliyor")
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            return True
        except Exception:
            logging.exception("BLE001 service: email gönderimi başarısız oldu")
            return False


# Varsayılan tekil örnek (tüm WatcherService kullanır)
_DEFAULT_EMAIL_SENDER = EmailSenderService()


class WatcherService:
    def __init__(
        self,
        repository: Any,
        matching_service: HybridMatchingService,
        settings: Settings,
        profile_repository: SQLAlchemyProfileRepository | None = None,
        jobs_service: JobsService | None = None,
        discovery_service: LiveJobDiscoveryService | None = None,
    ) -> None:
        self.repository = repository
        self.matching_service = matching_service
        self.settings = settings
        self.profile_repository = profile_repository
        self.jobs_service = jobs_service
        self.discovery_service = discovery_service or LiveJobDiscoveryService()

    def list_watchers(self) -> list[WatcherRecord]:
        return self.repository.list_watchers()

    def create_watcher(self, payload: WatcherCreateRequest) -> WatcherRecord:
        now = utcnow()
        candidate_profile = payload.candidate_profile
        if candidate_profile is None:
            if payload.profile_id is None or self.profile_repository is None:
                raise ValueError(
                    "profile_id kullanımı için profil repository gereklidir."
                )
            candidate_profile = self.profile_repository.get_profile(
                payload.profile_id
            ).profile
        watcher = WatcherRecord(
            id=f"watcher-{uuid4().hex[:12]}",
            user_id=payload.user_id,
            query_name=payload.query_name,
            source_platform=payload.source_platform,
            search_criteria=payload.search_criteria,
            candidate_profile=candidate_profile,
            weights=payload.weights,
            minimum_match_score=payload.minimum_match_score,
            sync_frequency_minutes=payload.sync_frequency_minutes,
            notification_channels=payload.notification_channels,
            created_at=now,
            updated_at=now,
            metadata={
                **payload.metadata,
                **({"profile_id": payload.profile_id} if payload.profile_id else {}),
            },
        )
        return self.repository.save_watcher(watcher)

    def update_watcher(
        self, watcher_id: str, payload: WatcherUpdateRequest
    ) -> WatcherRecord:
        watcher = self.repository.get_watcher(watcher_id)
        updated = watcher.model_copy(
            update={
                key: value
                for key, value in {
                    "query_name": payload.query_name,
                    "search_criteria": payload.search_criteria,
                    "minimum_match_score": payload.minimum_match_score,
                    "sync_frequency_minutes": payload.sync_frequency_minutes,
                    "notification_channels": payload.notification_channels,
                    "is_active": payload.is_active,
                    "updated_at": utcnow(),
                }.items()
                if value is not None
            }
        )
        return self.repository.save_watcher(updated)

    def delete_watcher(self, watcher_id: str) -> bool:
        return self.repository.delete_watcher(watcher_id)

    def toggle_watcher_active(self, watcher_id: str, is_active: bool) -> WatcherRecord:
        watcher = self.repository.get_watcher(watcher_id)
        updated = watcher.model_copy(
            update={"is_active": is_active, "updated_at": utcnow()}
        )
        return self.repository.save_watcher(updated)

    # ---------- İşlem Logları (Operation Logs) ----------
    def log_event(self, payload: LogCreateRequest) -> OperationLogRecord:
        return self.repository.log_event(
            level=str(payload.level or "INFO").upper(),
            source=payload.source or "api",
            message=payload.message,
            user_id=payload.user_id,
            watcher_id=payload.watcher_id,
            metadata=payload.metadata or {},
        )

    def list_logs(
        self,
        *,
        level: str | None = None,
        source: str | None = None,
        user_id: str | None = None,
        watcher_id: str | None = None,
        limit: int = 100,
    ) -> list[OperationLogRecord]:
        return self.repository.list_logs(
            level=level,
            source=source,
            user_id=user_id,
            watcher_id=watcher_id,
            limit=limit,
        )

    def list_runs(self, watcher_id: str) -> list[SyncRunRecord]:
        return self.repository.list_runs(watcher_id)

    def list_archive(self, user_id: str | None = None) -> list[ArchiveRecord]:
        return self.repository.list_archive(user_id)

    def get_archive_detail(self, user_id: str, job_id: str) -> ArchiveJobDetailResponse:
        archive = self.repository.get_archive(user_id, job_id)
        if archive is None:
            raise KeyError(job_id)
        return ArchiveJobDetailResponse(
            archive=archive,
            notifications=self.repository.get_job_notifications(user_id, job_id),
        )

    def list_notifications(
        self, user_id: str | None = None
    ) -> list[NotificationRecord]:
        return self.repository.list_notifications(user_id)

    def run_watcher(
        self, watcher_id: str, payload: WatcherRunRequest
    ) -> WatcherRunResponse:
        watcher = self.repository.get_watcher(watcher_id)
        run = SyncRunRecord(
            id=f"run-{uuid4().hex[:12]}",
            watcher_id=watcher.id,
            user_id=watcher.user_id,
            status=SyncStatus.running,
            started_at=utcnow(),
            metadata={"triggered_by": payload.triggered_by},
        )
        self.repository.add_run(run)
        run_src = (
            "scheduler"
            if str(payload.triggered_by or "").casefold().startswith("schedule")
            else "api"
        )
        try:
            self.repository.log_event(
                level="INFO",
                source=run_src,
                user_id=watcher.user_id,
                watcher_id=watcher.id,
                message=f"Run başladı · {len(payload.jobs)} adet iş · trigger={payload.triggered_by or 'manual'}",
                metadata={
                    "jobs_count": len(payload.jobs),
                    "triggered_by": payload.triggered_by,
                },
            )
            filtered_jobs = self._filter_jobs(
                payload.jobs, watcher.search_criteria, watcher.source_platform
            )
            if filtered_jobs:
                match_response = self.matching_service.match_jobs(
                    MatchRequest(
                        candidate=watcher.candidate_profile,
                        jobs=filtered_jobs,
                        weights=watcher.weights,
                        top_k=min(len(filtered_jobs), 50),
                    )
                )
            else:
                match_response = None

            archived_records: list[ArchiveRecord] = []
            notifications: list[NotificationRecord] = []
            if match_response is not None:
                for result in match_response.results:
                    if result.total_score < watcher.minimum_match_score:
                        continue
                    job = next(
                        job for job in filtered_jobs if job.job_id == result.job_id
                    )
                    archive_record = self._upsert_archive(
                        watcher, job, result.total_score, result.recommendation.value
                    )
                    archived_records.append(archive_record)
                    notifications.extend(
                        self._create_notifications(
                            watcher, archive_record, result.total_score
                        )
                    )
            if archived_records:
                self.repository.log_event(
                    level="INFO",
                    source="match",
                    user_id=watcher.user_id,
                    watcher_id=watcher.id,
                    message=f"Match tamamlandı · {len(archived_records)} archive · {len(notifications)} bildirim · "
                    f"filtreli {len(filtered_jobs)} iş",
                    metadata={
                        "filtered": len(filtered_jobs or []),
                        "archived": len(archived_records),
                        "notifications": len(notifications),
                        "titles": [(r.title or "")[:80] for r in archived_records[:10]],
                    },
                )

            finished_run = run.model_copy(
                update={
                    "status": SyncStatus.completed,
                    "finished_at": utcnow(),
                    "processed_jobs": len(payload.jobs),
                    "matched_jobs": len(archived_records),
                    "notifications_created": len(notifications),
                }
            )
            self._replace_run(finished_run)

            updated_watcher = watcher.model_copy(
                update={"last_synced_at": utcnow(), "updated_at": utcnow()}
            )
            self.repository.save_watcher(updated_watcher)
            self.repository.log_event(
                level="INFO",
                source=run_src,
                user_id=watcher.user_id,
                watcher_id=watcher.id,
                message=f"Run tamamlandı · {len(payload.jobs)} iş · {len(archived_records)} match · "
                f"{len(notifications)} bildirim",
                metadata={
                    "processed": len(payload.jobs),
                    "matched": len(archived_records),
                    "notifications": len(notifications),
                    "duration_ms": int(
                        (
                            finished_run.finished_at - finished_run.started_at
                        ).total_seconds()
                        * 1000
                    )
                    if finished_run.finished_at and finished_run.started_at
                    else 0,
                },
            )
            return WatcherRunResponse(
                watcher=updated_watcher,
                run=finished_run,
                archived_jobs=archived_records,
                notifications=notifications,
            )
        except Exception as exc:
            self.repository.log_event(
                level="ERROR",
                source=run_src,
                user_id=getattr(watcher, "user_id", None),
                watcher_id=getattr(watcher, "id", None),
                message=f"Run HATASI · {exc.__class__.__name__}: {str(exc)[:240]}",
                metadata={"error_type": exc.__class__.__name__},
            )
            failed_run = run.model_copy(
                update={
                    "status": SyncStatus.failed,
                    "finished_at": utcnow(),
                    "processed_jobs": len(payload.jobs),
                    "error_message": str(exc),
                }
            )
            self._replace_run(failed_run)
            raise

    def discover_jobs(
        self, watcher_id: str, payload: WatcherDiscoverRequest
    ) -> WatcherDiscoverResponse:
        watcher = self.repository.get_watcher(watcher_id)
        if self.jobs_service is None:
            raise ValueError("Canlı keşif için jobs service gereklidir.")

        source_urls = payload.source_urls or self._extract_source_urls(watcher)
        if not source_urls:
            raise ValueError(
                "Canlı keşif için en az bir izinli kaynak URL'si tanımlanmalıdır."
            )
        self.repository.log_event(
            level="INFO",
            source="discovery",
            user_id=watcher.user_id,
            watcher_id=watcher.id,
            message=f"Discovery başladı · {len(source_urls)} URL · max_jobs={payload.max_jobs}",
            metadata={
                "urls": source_urls,
                "max_jobs": payload.max_jobs,
                "triggered_by": payload.triggered_by,
            },
        )
        discovered_jobs, source_reports = self.discovery_service.discover(
            source_urls, max_jobs=payload.max_jobs
        )
        active_discovered_jobs = [
            job for job in discovered_jobs if self._is_discovered_job_active(job)
        ]
        skipped_inactive_jobs = len(discovered_jobs) - len(active_discovered_jobs)
        imported_jobs = [
            self._import_discovered_job(watcher, job) for job in active_discovered_jobs
        ]
        parsed_jobs = [
            job.parsed_job.model_copy(
                update={
                    "metadata": {
                        **(job.parsed_job.metadata or {}),
                        "company_name": job.company_name,
                        "source_platform": job.source_platform.value,
                        "position_type": job.metadata.get("position_type", "full-time"),
                    }
                }
            )
            for job in imported_jobs
        ]
        run_response = self.run_watcher(
            watcher_id,
            WatcherRunRequest(
                jobs=parsed_jobs,
                triggered_by=payload.triggered_by,
            ),
        )
        run_response.run.metadata.update(
            {
                "source_urls": source_urls,
                "source_reports": [
                    report.model_dump(mode="json") for report in source_reports
                ],
                "inactive_jobs_skipped": skipped_inactive_jobs,
            }
        )
        self._replace_run(run_response.run)
        self.repository.log_event(
            level="INFO",
            source="discovery",
            user_id=watcher.user_id,
            watcher_id=watcher.id,
            message=f"Discovery bitti · {len(discovered_jobs)} ham · {len(active_discovered_jobs)} aktif · "
            f"{skipped_inactive_jobs} pasif atlandı · archive={len(run_response.archived_jobs)}",
            metadata={
                "raw": len(discovered_jobs),
                "active": len(active_discovered_jobs),
                "skipped_inactive": skipped_inactive_jobs,
                "archived": len(run_response.archived_jobs),
                "reports": [
                    {
                        "url": r.source_url,
                        "ok": getattr(r.status, "value", r.status),
                        "count": getattr(r, "fetched_jobs", getattr(r, "job_count", 0)),
                    }
                    for r in source_reports
                ][:10],
            },
        )

        return WatcherDiscoverResponse(
            watcher=run_response.watcher,
            run=run_response.run,
            archived_jobs=run_response.archived_jobs,
            notifications=run_response.notifications,
            imported_jobs=imported_jobs,
            source_reports=source_reports,
        )

    def _replace_run(self, run: SyncRunRecord) -> None:
        self.repository.update_run(run)

    def _filter_jobs(
        self,
        jobs,
        criteria: SearchCriteria,
        source_platform: SourcePlatform,
    ):
        filtered = []
        keyword_tokens = [
            [token for token in keyword.casefold().replace(",", " ").split() if token]
            for keyword in criteria.keywords
            if keyword and keyword.strip()
        ]
        location_filters = [location.casefold() for location in criteria.locations]
        industry_filters = {industry.casefold() for industry in criteria.industries}
        work_mode_filters = {mode.value for mode in criteria.work_modes}
        position_types = {item.casefold() for item in criteria.position_types}

        generic_location_tokens = {"remote", "anywhere", "worldwide", "global"}
        uses_generic_location = any(
            any(tok in allowed for tok in generic_location_tokens)
            for allowed in location_filters
            if allowed
        )

        def job_location_matches(job_location: str) -> bool:
            if not location_filters:
                return True
            loc = (job_location or "").casefold()
            if not loc:
                return True
            for allowed in location_filters:
                if not allowed:
                    continue
                if allowed == loc:
                    return True
                if allowed in loc:
                    return True
                if loc in allowed:
                    return True
                allowed_tokens = [t for t in allowed.replace(",", " ").split() if t]
                if allowed_tokens and all(token in loc for token in allowed_tokens):
                    return True
            if uses_generic_location and any(
                tok in loc for tok in generic_location_tokens
            ):
                return True
            return False

        def keyword_match(title: str, haystack: str) -> bool:
            if not keyword_tokens:
                return True
            hay = haystack.casefold()
            ttl = title.casefold()
            for tokens in keyword_tokens:
                if not tokens:
                    continue
                if len(tokens) == 1:
                    if tokens[0] in hay or tokens[0] in ttl:
                        return True
                else:
                    if all(tok in hay for tok in tokens):
                        return True
                    if all(tok in ttl for tok in tokens):
                        return True
            return False

        for job in jobs:
            title = (job.title or "").casefold()
            description = (job.description or "").casefold()
            requirements = (job.requirements or "").casefold()
            raw_text_snippet = (getattr(job, "raw_text", "") or "").casefold()
            haystack = f"{title} {description} {requirements} {raw_text_snippet}"

            if not keyword_match(title, haystack):
                continue

            if not job_location_matches(job.location or ""):
                continue

            if industry_filters:
                job_industries = {
                    (industry or "").casefold() for industry in (job.industries or [])
                }
                intersection = job_industries & industry_filters
                if not intersection and job_industries:
                    continue

            if work_mode_filters:
                mode = (job.work_mode.value or "").casefold()
                location = (job.location or "").casefold()
                mode_passes = mode in work_mode_filters
                if not mode_passes:
                    if (
                        "remote" in work_mode_filters
                        and "remote" in location
                        or "hybrid" in work_mode_filters
                        and "hybrid" in location
                        or "remote" in work_mode_filters
                        and (
                            "anywhere" in location
                            or "global" in location
                            or "worldwide" in location
                        )
                    ):
                        mode_passes = True
                if not mode_passes:
                    continue

            if criteria.min_experience_years is not None:
                required = job.min_years_experience or 0
                if required > criteria.min_experience_years + 15:
                    continue

            if position_types and job.metadata.get("position_type"):
                if (
                    job.metadata.get("position_type") or ""
                ).casefold() not in position_types:
                    continue

            enriched = job.model_copy(
                update={
                    "metadata": {
                        **job.metadata,
                        "source_platform": source_platform.value,
                    }
                }
            )
            filtered.append(enriched)
        return filtered

    def _extract_source_urls(self, watcher: WatcherRecord) -> list[str]:
        source_urls = watcher.metadata.get("source_urls", [])
        if not isinstance(source_urls, list):
            return []
        return [str(item).strip() for item in source_urls if str(item).strip()]

    def _is_discovered_job_active(self, job: DiscoveredJobInput) -> bool:
        metadata = job.metadata or {}

        application_open = metadata.get("application_open")
        if isinstance(application_open, bool) and not application_open:
            return False

        accepting_applications = metadata.get("accepting_applications")
        if isinstance(accepting_applications, bool) and not accepting_applications:
            return False

        expires_at = self._parse_optional_datetime(metadata.get("expires_at"))
        if expires_at is not None:
            return expires_at >= utcnow()

        is_active = metadata.get("is_active")
        if isinstance(is_active, bool):
            return is_active
        return True

    def _parse_optional_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _import_discovered_job(self, watcher: WatcherRecord, job: DiscoveredJobInput):
        profile_id = watcher.metadata.get("profile_id")
        assert self.jobs_service is not None, (
            "jobs_service dependency required for import"
        )
        return self.jobs_service.import_job(
            JobImportRequest(
                user_id=watcher.user_id,
                profile_id=str(profile_id) if profile_id else None,
                title=job.title,
                company_name=job.company_name,
                source_platform=job.source_platform,
                source_url=job.source_url,
                location=job.location,
                work_mode=job.work_mode,
                language=job.language,
                raw_text=job.raw_text,
                metadata={
                    **job.metadata,
                    "watcher_id": watcher.id,
                    "discovered_live": True,
                    "discovered_platform": job.source_platform.value,
                    "search_verified": True,
                },
            ),
            candidate=watcher.candidate_profile,
        )

    def _upsert_archive(
        self, watcher: WatcherRecord, job, total_score: float, recommendation: str
    ) -> ArchiveRecord:
        existing = self.repository.get_archive(watcher.user_id, job.job_id)
        now = utcnow()
        job_metadata = job.metadata if isinstance(job.metadata, dict) else {}
        job_source_url = job_metadata.get("source_url") or (
            job.source_url if hasattr(job, "source_url") and job.source_url else None
        )
        job_apply_url = job_metadata.get("apply_url") or (
            job.apply_url if hasattr(job, "apply_url") and job.apply_url else None
        )
        base_metadata = {
            "work_mode": job.work_mode.value,
            "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills,
        }
        if job_source_url:
            base_metadata["source_url"] = job_source_url
        if job_apply_url:
            base_metadata["apply_url"] = job_apply_url

        if existing is None:
            archive = ArchiveRecord(
                user_id=watcher.user_id,
                watcher_id=watcher.id,
                job_id=job.job_id,
                title=job.title,
                company_name=job.metadata.get("company_name", "Bilinmiyor"),
                location=job.location,
                source_platform=job.metadata.get(
                    "source_platform", watcher.source_platform.value
                ),
                source_url=job_source_url,
                apply_url=job_apply_url,
                first_seen_at=now,
                last_seen_at=now,
                notification_sent=False,
                last_match_score=total_score,
                last_recommendation=recommendation,
                metadata=base_metadata,
            )
        else:
            archive = existing.model_copy(
                update={
                    "source_url": job_source_url or existing.source_url,
                    "apply_url": job_apply_url or existing.apply_url,
                    "last_seen_at": now,
                    "last_match_score": total_score,
                    "last_recommendation": recommendation,
                    "metadata": {**existing.metadata, **base_metadata},
                }
            )
        return self.repository.save_archive(archive)

    def _create_notifications(
        self,
        watcher: WatcherRecord,
        archive: ArchiveRecord,
        total_score: float,
    ) -> list[NotificationRecord]:
        notifications: list[NotificationRecord] = []
        if archive.notification_sent:
            return notifications

        # Hedef email adresi (öncelik: metadata.user_email > user_id email görünümünde ise)
        user_email: str | None = None
        if isinstance(watcher.metadata, dict):
            user_email = str(
                watcher.metadata.get("user_email")
                or watcher.metadata.get("email")
                or ""
            ).strip()
        if not user_email and "@" in (watcher.user_id or ""):
            user_email = watcher.user_id.strip()

        for channel in watcher.notification_channels:
            notification = NotificationRecord(
                id=f"notif-{uuid4().hex[:12]}",
                user_id=watcher.user_id,
                watcher_id=watcher.id,
                job_id=archive.job_id,
                channel=channel,
                title=f"Yeni yüksek eşleşme: {archive.title}",
                message=f"{archive.title} ilanı {total_score:.2f} skor ile eşik değeri aştı.",
                created_at=utcnow(),
                metadata={
                    "company_name": archive.company_name,
                    "source_platform": archive.source_platform,
                },
            )
            saved = self.repository.add_notification(notification)
            notifications.append(saved)

            # Email channel ise GERÇEKTEN SMTP ile gönder (env yoksa sessizce atlar)
            if channel == NotificationChannel.email and user_email:
                try:
                    ok = _DEFAULT_EMAIL_SENDER.send_match_notification(
                        user_email, archive, total_score
                    )
                    if ok:
                        md = dict(saved.metadata or {})
                        md["email_sent_at"] = utcnow().isoformat()
                        object.__setattr__(saved, "metadata", md)
                        try:
                            self.repository.save_notification(saved)
                        except Exception:
                            logging.exception("BLE001 service: bildirim kaydedilemedi (email metadata update)")
                        self.repository.log_event(
                            level="INFO",
                            source="email",
                            user_id=watcher.user_id,
                            watcher_id=watcher.id,
                            message=f"Email OK → {user_email} · %{total_score:.1f} · {archive.title or ''[:60]}",
                            metadata={
                                "to": user_email,
                                "score": total_score,
                                "archive_job_id": archive.job_id,
                            },
                        )
                    else:
                        # SMTP ayarlanmamış (is_configured=False) veya gönderim başarısız False dönen
                        if _DEFAULT_EMAIL_SENDER.is_configured:
                            self.repository.log_event(
                                level="WARN",
                                source="email",
                                user_id=watcher.user_id,
                                watcher_id=watcher.id,
                                message=f"Email gönderilemedi (False döndü) · {user_email}",
                                metadata={"to": user_email, "smtp_configured": True},
                            )
                except Exception as exc:
                    self.repository.log_event(
                        level="ERROR",
                        source="email",
                        user_id=watcher.user_id,
                        watcher_id=watcher.id,
                        message=f"Email HATASI · {exc.__class__.__name__}: {str(exc)[:200]}",
                        metadata={
                            "to": user_email,
                            "error_type": exc.__class__.__name__,
                        },
                    )

        updated_archive = archive.model_copy(
            update={
                "notification_sent": True,
                "notifications_sent": archive.notifications_sent + len(notifications),
            }
        )
        self.repository.save_archive(updated_archive)
        return notifications

    # ── Bildirim Okuma/Listeme ──────────────────────────────────────────

    def get_notification(
        self, notification_id: str, user_id: str | None = None
    ) -> NotificationRecord | None:
        """ID'ye göre bildirim bul. user_id verilirse kullanıcı doğrulaması yap."""
        item = self.repository.get_notification(notification_id)
        if item is None:
            return None
        if user_id and item.user_id != user_id:
            return None
        return item

    def mark_notification_read(
        self, notification_id: str, user_id: str | None = None, is_read: bool = True
    ) -> NotificationRecord | None:
        """Bir bildirimi okunmuş/okunmamış işaretle. user_id verilmezse doğrulama ATLA (kısa devre)."""
        item = self.repository.get_notification(notification_id)
        if item is None:
            return None
        if user_id and item.user_id != user_id:
            return None
        return self.repository.update_notification_is_read(
            notification_id, is_read=is_read
        )

    def mark_all_notifications_read(self, user_id: str) -> int:
        """Kullanıcıya ait TÜM okunmamış bildirimleri okunmuş yap — kaç adet olduğunu döner."""
        if not user_id:
            return 0
        return self.repository.mark_all_notifications_read(user_id)
