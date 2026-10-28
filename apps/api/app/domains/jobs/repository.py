from __future__ import annotations

from datetime import timezone

from sqlalchemy import delete, select

from ...core.database import SessionLocal
from .models import ApplicationModel, JobModel
from .schemas import ApplicationRecord, JobRecord


class SQLAlchemyJobsRepository:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def save_job(self, record: JobRecord) -> JobRecord:
        with self.session_factory() as session:
            row = session.get(JobModel, record.id)
            data = record.model_dump(mode="json")
            if row is None:
                row = JobModel(
                    id=data["id"],
                    user_id=data["user_id"],
                    profile_id=data["profile_id"],
                    title=data["title"],
                    company_name=data["company_name"],
                    source_platform=data["source_platform"],
                    source_url=data["source_url"],
                    location=data["location"],
                    work_mode=data["work_mode"],
                    language=data["language"],
                    raw_text=data["raw_text"],
                    parsed_job_json=data["parsed_job"],
                    analysis_result_json=data["analysis_result"],
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    metadata_json=data["metadata"],
                )
                session.add(row)
            else:
                row.profile_id = data["profile_id"]
                row.title = data["title"]
                row.company_name = data["company_name"]
                row.source_platform = data["source_platform"]
                row.source_url = data["source_url"]
                row.location = data["location"]
                row.work_mode = data["work_mode"]
                row.language = data["language"]
                row.raw_text = data["raw_text"]
                row.parsed_job_json = data["parsed_job"]
                row.analysis_result_json = data["analysis_result"]
                row.updated_at = record.updated_at
                row.metadata_json = data["metadata"]
            session.commit()
            return self._to_job_record(row)

    def get_job(self, job_id: str) -> JobRecord:
        with self.session_factory() as session:
            row = session.get(JobModel, job_id)
            if row is None:
                raise KeyError(job_id)
            return self._to_job_record(row)

    def list_jobs(self, user_id: str | None = None) -> list[JobRecord]:
        with self.session_factory() as session:
            stmt = select(JobModel).order_by(JobModel.updated_at.desc())
            if user_id:
                stmt = stmt.where(JobModel.user_id == user_id)
            rows = session.scalars(stmt).all()
            return [self._to_job_record(row) for row in rows]

    def save_application(self, record: ApplicationRecord) -> ApplicationRecord:
        with self.session_factory() as session:
            row = session.get(ApplicationModel, record.id)
            data = record.model_dump(mode="json")
            if row is None:
                row = ApplicationModel(
                    id=data["id"],
                    user_id=data["user_id"],
                    job_id=data["job_id"],
                    status=data["status"],
                    notes=data["notes"],
                    contact_person=data["contact_person"],
                    expected_salary=data["expected_salary"],
                    offered_salary=data["offered_salary"],
                    reminder_at=record.reminder_at,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    metadata_json=data["metadata"],
                )
                session.add(row)
            else:
                row.status = data["status"]
                row.notes = data["notes"]
                row.contact_person = data["contact_person"]
                row.expected_salary = data["expected_salary"]
                row.offered_salary = data["offered_salary"]
                row.reminder_at = record.reminder_at
                row.updated_at = record.updated_at
                row.metadata_json = data["metadata"]
            session.commit()
            return self._to_application_record(row)

    def get_application(self, application_id: str) -> ApplicationRecord:
        with self.session_factory() as session:
            row = session.get(ApplicationModel, application_id)
            if row is None:
                raise KeyError(application_id)
            return self._to_application_record(row)

    def list_applications(self, user_id: str | None = None) -> list[ApplicationRecord]:
        with self.session_factory() as session:
            stmt = select(ApplicationModel).order_by(ApplicationModel.updated_at.desc())
            if user_id:
                stmt = stmt.where(ApplicationModel.user_id == user_id)
            rows = session.scalars(stmt).all()
            return [self._to_application_record(row) for row in rows]

    def clear_all(self) -> None:
        with self.session_factory() as session:
            session.execute(delete(ApplicationModel))
            session.execute(delete(JobModel))
            session.commit()

    def _to_job_record(self, row: JobModel) -> JobRecord:
        return JobRecord.model_validate(
            {
                "id": row.id,
                "user_id": row.user_id,
                "profile_id": row.profile_id,
                "title": row.title,
                "company_name": row.company_name,
                "source_platform": row.source_platform,
                "source_url": row.source_url,
                "location": row.location,
                "work_mode": row.work_mode,
                "language": row.language,
                "raw_text": row.raw_text,
                "parsed_job": row.parsed_job_json,
                "analysis_result": row.analysis_result_json,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": row.metadata_json or {},
            }
        )

    def _to_application_record(self, row: ApplicationModel) -> ApplicationRecord:
        reminder_at = row.reminder_at
        if reminder_at is not None and reminder_at.tzinfo is None:
            reminder_at = reminder_at.replace(tzinfo=timezone.utc)

        return ApplicationRecord.model_validate(
            {
                "id": row.id,
                "user_id": row.user_id,
                "job_id": row.job_id,
                "status": row.status,
                "notes": row.notes,
                "contact_person": row.contact_person,
                "expected_salary": row.expected_salary,
                "offered_salary": row.offered_salary,
                "reminder_at": reminder_at,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": row.metadata_json or {},
            }
        )


jobs_repository = SQLAlchemyJobsRepository()
