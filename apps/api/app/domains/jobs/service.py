from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ..matching.schemas import CandidateProfileInput, MatchRequest
from ..matching.service import HybridMatchingService
from ..profile.repository import SQLAlchemyProfileRepository
from .parser import JobParser
from .repository import SQLAlchemyJobsRepository
from .schemas import (
    ApplicationCreateRequest,
    ApplicationRecord,
    ApplicationUpdateRequest,
    JobAnalysisRequest,
    JobDetailResponse,
    JobImportRequest,
    JobRecord,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobsService:
    def __init__(
        self,
        repository: SQLAlchemyJobsRepository,
        profile_repository: SQLAlchemyProfileRepository,
        matching_service: HybridMatchingService,
        parser: JobParser,
    ) -> None:
        self.repository = repository
        self.profile_repository = profile_repository
        self.matching_service = matching_service
        self.parser = parser

    def import_job(
        self, payload: JobImportRequest, candidate: CandidateProfileInput | None = None
    ) -> JobRecord:
        parsed_job = self.parser.parse(payload)
        now = utcnow()
        record = JobRecord(
            id=parsed_job.job_id,
            user_id=payload.user_id,
            profile_id=payload.profile_id,
            title=payload.title,
            company_name=payload.company_name,
            source_platform=payload.source_platform,
            source_url=payload.source_url,
            location=payload.location,
            work_mode=payload.work_mode or parsed_job.work_mode,
            language=payload.language,
            raw_text=payload.raw_text,
            parsed_job=parsed_job,
            analysis_result=None,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata,
        )
        saved = self.repository.save_job(record)
        if payload.profile_id:
            return self.analyze_job(
                saved.id, JobAnalysisRequest(profile_id=payload.profile_id)
            ).job
        if candidate is not None:
            return self._analyze_job_for_candidate(saved, candidate)
        return saved

    def analyze_job(
        self, job_id: str, payload: JobAnalysisRequest
    ) -> JobDetailResponse:
        job = self._refresh_job_activity_state(self.repository.get_job(job_id))
        profile = self.profile_repository.get_profile(payload.profile_id)
        return JobDetailResponse(
            job=self._analyze_job_for_candidate(
                job, profile.profile, profile_id=payload.profile_id
            )
        )

    def _analyze_job_for_candidate(
        self,
        job: JobRecord,
        candidate: CandidateProfileInput,
        *,
        profile_id: str | None = None,
    ) -> JobRecord:
        match_response = self.matching_service.match_jobs(
            MatchRequest(candidate=candidate, jobs=[job.parsed_job], top_k=1)
        )
        match_result = match_response.results[0]
        updated = job.model_copy(
            update={
                "profile_id": profile_id or job.profile_id,
                "analysis_result": match_result,
                "updated_at": utcnow(),
            }
        )
        return self.repository.save_job(updated)

    def list_jobs(
        self,
        user_id: str | None = None,
        *,
        active_only: bool = False,
        published_within_days: int | None = None,
        source_platforms: list[str] | None = None,
        search: str | None = None,
        sort_by: str = "published_at",
        sort_order: str = "desc",
        dedupe: bool = False,
    ) -> list[JobRecord]:
        jobs = self.repository.list_jobs(user_id=user_id)
        filtered: list[JobRecord] = []
        source_filter = {item.casefold() for item in (source_platforms or []) if item}
        search_value = (search or "").casefold().strip()
        published_cutoff = None
        if published_within_days is not None:
            published_cutoff = utcnow() - timedelta(days=published_within_days)

        for job in jobs:
            job = self._refresh_job_activity_state(job)
            metadata = job.metadata or {}
            is_active = self._is_job_active(job)
            published_at = self._parse_optional_datetime(
                metadata.get("published_at")
            ) or self._ensure_aware(job.created_at)

            if active_only and not is_active:
                continue
            if published_cutoff is not None:
                if published_at is None or published_at < published_cutoff:
                    continue
            if (
                source_filter
                and job.source_platform.value.casefold() not in source_filter
            ):
                continue
            if search_value:
                haystack = " ".join(
                    [
                        job.title,
                        job.company_name,
                        job.location,
                        job.raw_text,
                        " ".join(job.parsed_job.required_skills),
                        " ".join(job.parsed_job.preferred_skills),
                    ]
                ).casefold()
                if search_value not in haystack:
                    continue
            filtered.append(job)

        if dedupe:
            deduped: list[JobRecord] = []
            seen_keys: set[tuple[str, str, str]] = set()
            for job in filtered:
                key = (
                    job.title.casefold(),
                    job.company_name.casefold(),
                    (job.source_url or "").split("?")[0],
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(job)
            filtered = deduped

        reverse = sort_order.casefold() != "asc"
        filtered.sort(key=lambda job: self._sort_key(job, sort_by), reverse=reverse)
        return filtered

    def get_job(self, job_id: str) -> JobDetailResponse:
        return JobDetailResponse(
            job=self._refresh_job_activity_state(self.repository.get_job(job_id))
        )

    def create_application(
        self, payload: ApplicationCreateRequest
    ) -> ApplicationRecord:
        job = self._refresh_job_activity_state(self.repository.get_job(payload.job_id))
        if not self._is_job_active(job):
            raise ValueError("Bu ilan artık başvuruya açık değil.")
        now = utcnow()
        record = ApplicationRecord(
            id=f"application-{uuid4().hex[:12]}",
            user_id=payload.user_id,
            job_id=payload.job_id,
            status=payload.status,
            notes=payload.notes,
            contact_person=payload.contact_person,
            expected_salary=payload.expected_salary,
            offered_salary=payload.offered_salary,
            reminder_at=payload.reminder_at,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata,
        )
        return self.repository.save_application(record)

    def update_application(
        self, application_id: str, payload: ApplicationUpdateRequest
    ) -> ApplicationRecord:
        application = self.repository.get_application(application_id)
        update_data = payload.model_dump(exclude_none=True)
        metadata = update_data.pop("metadata", None)
        updated = application.model_copy(
            update={
                **update_data,
                "updated_at": utcnow(),
                "metadata": {**application.metadata, **(metadata or {})},
            }
        )
        return self.repository.save_application(updated)

    def list_applications(self, user_id: str | None = None) -> list[ApplicationRecord]:
        return self.repository.list_applications(user_id=user_id)

    def _sort_key(self, job: JobRecord, sort_by: str):
        metadata = job.metadata or {}
        if sort_by == "score":
            return job.analysis_result.total_score if job.analysis_result else -1
        if sort_by == "company_name":
            return job.company_name.casefold()
        if sort_by == "title":
            return job.title.casefold()
        if sort_by == "updated_at":
            return job.updated_at
        published_at = self._parse_optional_datetime(
            metadata.get("published_at")
        ) or self._ensure_aware(job.created_at)
        return published_at

    def _is_job_active(self, job: JobRecord) -> bool:
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

    def _ensure_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _refresh_job_activity_state(self, job: JobRecord) -> JobRecord:
        metadata = dict(job.metadata or {})
        expected_is_active = self._is_job_active(job)
        if metadata.get("is_active") == expected_is_active:
            return job
        updated = job.model_copy(
            update={"metadata": {**metadata, "is_active": expected_is_active}}
        )
        return self.repository.save_job(updated)
