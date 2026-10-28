from __future__ import annotations

from sqlalchemy import delete, select

from ...core.database import SessionLocal
from .models import CandidateProfileModel, CvFileModel
from .schemas import CandidateProfileRecord, CvFileRecord


class SQLAlchemyProfileRepository:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def save_cv_file(self, record: CvFileRecord) -> CvFileRecord:
        with self.session_factory() as session:
            row = session.get(CvFileModel, record.id)
            data = record.model_dump(mode="json")
            if row is None:
                row = CvFileModel(
                    id=data["id"],
                    user_id=data["user_id"],
                    filename=data["filename"],
                    content_type=data["content_type"],
                    storage_path=data["storage_path"],
                    language=data["language"],
                    parse_status=data["parse_status"],
                    extracted_text=data["extracted_text"],
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    metadata_json=data["metadata"],
                )
                session.add(row)
            else:
                row.filename = data["filename"]
                row.content_type = data["content_type"]
                row.storage_path = data["storage_path"]
                row.language = data["language"]
                row.parse_status = data["parse_status"]
                row.extracted_text = data["extracted_text"]
                row.updated_at = record.updated_at
                row.metadata_json = data["metadata"]
            session.commit()
            return self._to_cv_file(row)

    def get_cv_file(self, file_id: str) -> CvFileRecord:
        with self.session_factory() as session:
            row = session.get(CvFileModel, file_id)
            if row is None:
                raise KeyError(file_id)
            return self._to_cv_file(row)

    def save_profile(self, record: CandidateProfileRecord) -> CandidateProfileRecord:
        with self.session_factory() as session:
            row = session.get(CandidateProfileModel, record.id)
            data = record.model_dump(mode="json")
            if row is None:
                row = CandidateProfileModel(
                    id=data["id"],
                    user_id=data["user_id"],
                    cv_file_id=data["cv_file_id"],
                    profile_json=data["profile"],
                    professional_summary=data["professional_summary"],
                    target_positions=data["target_positions"],
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    metadata_json=data["metadata"],
                )
                session.add(row)
            else:
                row.user_id = data["user_id"]
                row.cv_file_id = data["cv_file_id"]
                row.profile_json = data["profile"]
                row.professional_summary = data["professional_summary"]
                row.target_positions = data["target_positions"]
                row.updated_at = record.updated_at
                row.metadata_json = data["metadata"]
            session.commit()
            return self._to_profile(row)

    def get_profile(self, profile_id: str) -> CandidateProfileRecord:
        with self.session_factory() as session:
            row = session.get(CandidateProfileModel, profile_id)
            if row is None:
                raise KeyError(profile_id)
            return self._to_profile(row)

    def get_latest_profile_by_user(self, user_id: str) -> CandidateProfileRecord:
        with self.session_factory() as session:
            row = session.scalar(
                select(CandidateProfileModel)
                .where(CandidateProfileModel.user_id == user_id)
                .order_by(CandidateProfileModel.updated_at.desc())
            )
            if row is None:
                raise KeyError(user_id)
            return self._to_profile(row)

    def clear_all(self) -> None:
        with self.session_factory() as session:
            session.execute(delete(CandidateProfileModel))
            session.execute(delete(CvFileModel))
            session.commit()

    def _to_cv_file(self, row: CvFileModel) -> CvFileRecord:
        return CvFileRecord.model_validate(
            {
                "id": row.id,
                "user_id": row.user_id,
                "filename": row.filename,
                "content_type": row.content_type,
                "storage_path": row.storage_path,
                "language": row.language,
                "parse_status": row.parse_status,
                "extracted_text": row.extracted_text,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": row.metadata_json or {},
            }
        )

    def _to_profile(self, row: CandidateProfileModel) -> CandidateProfileRecord:
        return CandidateProfileRecord.model_validate(
            {
                "id": row.id,
                "user_id": row.user_id,
                "cv_file_id": row.cv_file_id,
                "profile": row.profile_json,
                "professional_summary": row.professional_summary,
                "target_positions": row.target_positions or [],
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": row.metadata_json or {},
            }
        )


profile_repository = SQLAlchemyProfileRepository()
