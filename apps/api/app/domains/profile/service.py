from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ...core.config import Settings
from ..matching.schemas import CandidateProfileInput
from .parser import CvParser
from .repository import SQLAlchemyProfileRepository
from .schemas import (
    CandidateProfileRecord,
    CvFileRecord,
    CvParseStatus,
    ProfileUpdateRequest,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProfileService:
    def __init__(
        self,
        repository: SQLAlchemyProfileRepository,
        parser: CvParser,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.parser = parser
        self.settings = settings

    async def upload_cv(
        self, file: UploadFile, user_id: str, language: str = "tr"
    ) -> CvFileRecord:
        self._validate_file(file)
        file_id = f"cv-{uuid4().hex[:12]}"
        extension = Path(file.filename or "cv").suffix.lower()
        storage_dir = Path(self.settings.storage_dir) / "cv"
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_path = storage_dir / f"{file_id}{extension}"
        content = await file.read()
        storage_path.write_bytes(content)
        now = utcnow()
        record = CvFileRecord(
            id=file_id,
            user_id=user_id,
            filename=file.filename or storage_path.name,
            content_type=file.content_type
            or self._content_type_from_extension(extension),
            storage_path=str(storage_path),
            language=language,
            parse_status=CvParseStatus.uploaded,
            created_at=now,
            updated_at=now,
            metadata={"size_bytes": len(content)},
        )
        return self.repository.save_cv_file(record)

    def parse_cv(self, file_id: str) -> CandidateProfileRecord:
        cv_file = self.repository.get_cv_file(file_id)
        try:
            text = self.parser.extract_text(cv_file.storage_path)
            profile, professional_summary, target_positions = (
                self.parser.parse_candidate_profile(
                    text=text,
                    candidate_id=f"profile-{uuid4().hex[:12]}",
                )
            )
            now = utcnow()
            saved_file = self.repository.save_cv_file(
                cv_file.model_copy(
                    update={
                        "parse_status": CvParseStatus.parsed,
                        "extracted_text": text,
                        "updated_at": now,
                    }
                )
            )
            profile_record = CandidateProfileRecord(
                id=profile.candidate_id or f"profile-{uuid4().hex[:12]}",
                user_id=saved_file.user_id,
                cv_file_id=saved_file.id,
                profile=profile,
                professional_summary=professional_summary,
                target_positions=target_positions,
                created_at=now,
                updated_at=now,
                metadata={"source_filename": saved_file.filename},
            )
            return self.repository.save_profile(profile_record)
        except Exception as exc:
            self.repository.save_cv_file(
                cv_file.model_copy(
                    update={
                        "parse_status": CvParseStatus.failed,
                        "updated_at": utcnow(),
                        "metadata": {**cv_file.metadata, "error": str(exc)},
                    }
                )
            )
            raise

    def get_profile(
        self, profile_id: str | None = None, user_id: str | None = None
    ) -> CandidateProfileRecord:
        if profile_id:
            return self.repository.get_profile(profile_id)
        if user_id:
            return self.repository.get_latest_profile_by_user(user_id)
        raise ValueError("profile_id veya user_id zorunludur.")

    def update_profile(
        self, profile_id: str, payload: ProfileUpdateRequest
    ) -> CandidateProfileRecord:
        record = self.repository.get_profile(profile_id)
        profile_data = record.profile.model_dump()
        update_data = payload.model_dump(exclude_none=True)
        metadata = update_data.pop("metadata", None)
        profile_data.update(update_data)
        typed_profile = CandidateProfileInput.model_validate(profile_data)
        updated = record.model_copy(
            update={
                "profile": typed_profile,
                "professional_summary": self.parser._build_professional_summary(
                    typed_profile
                ),
                "updated_at": utcnow(),
                "metadata": {**record.metadata, **(metadata or {})},
            }
        )
        return self.repository.save_profile(updated)

    def get_cv_file(self, file_id: str) -> CvFileRecord:
        return self.repository.get_cv_file(file_id)

    def _validate_file(self, file: UploadFile) -> None:
        filename = file.filename or ""
        extension = Path(filename).suffix.lower()
        if extension not in {".pdf", ".docx"}:
            raise ValueError("Yalnızca PDF veya DOCX CV yüklenebilir.")

    def _content_type_from_extension(self, extension: str) -> str:
        if extension == ".pdf":
            return "application/pdf"
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
