from __future__ import annotations

import hashlib
import re

from ..matching.schemas import JobPostingInput, WorkMode
from .schemas import JobImportRequest

SKILL_KEYWORDS = [
    "python",
    "jira",
    "xray",
    "ci/cd",
    "selenium",
    "playwright",
    "postman",
    "api testing",
    "agile",
    "scrum",
    "test automation",
    "quality assurance",
    "qa",
    "fintech",
    "payment systems",
]
INDUSTRY_KEYWORDS = ["fintech", "e-commerce", "e-ticaret", "payment", "banking", "saas"]
EDUCATION_KEYWORDS = [
    "computer engineering",
    "software engineering",
    "bilgisayar mühendisliği",
]
CERTIFICATION_KEYWORDS = ["istqb", "psm", "pmp", "scrum master"]


class JobParser:
    def parse(self, payload: JobImportRequest) -> JobPostingInput:
        normalized = self._normalize(f"{payload.title}\n{payload.raw_text}")
        required_skills = self._collect_keywords(normalized, SKILL_KEYWORDS)
        min_years = self._extract_years(normalized)
        management_years = self._extract_management_years(normalized)
        work_mode = payload.work_mode or self._infer_work_mode(normalized)
        industries = self._collect_keywords(normalized, INDUSTRY_KEYWORDS)
        education = self._collect_keywords(normalized, EDUCATION_KEYWORDS)
        certs = self._collect_keywords(normalized, CERTIFICATION_KEYWORDS)
        job_id = self._build_job_id(
            user_id=payload.user_id,
            source_url=payload.source_url,
            title=payload.title,
            company_name=payload.company_name,
            location=payload.location,
            source_platform=payload.source_platform,
        )

        return JobPostingInput(
            job_id=job_id,
            title=payload.title,
            description=payload.raw_text[:500],
            requirements=payload.raw_text[:1200],
            required_skills=self._titleize_items(required_skills),
            preferred_skills=self._titleize_items(required_skills[2:5]),
            industries=self._titleize_items(industries),
            min_years_experience=min_years,
            management_years_required=management_years,
            location=payload.location,
            work_mode=work_mode,
            language_requirement=payload.language,
            salary_min=payload.salary_min,
            salary_max=payload.salary_max,
            education_requirements=self._titleize_items(education),
            certification_requirements=[
                item.upper() if item == "istqb" else item.title() for item in certs
            ],
            raw_text=payload.raw_text,
            metadata={
                "company_name": payload.company_name,
                "source_url": payload.source_url,
                **payload.metadata,
            },
        )

    def _build_job_id(
        self,
        *,
        user_id: str,
        source_url: str | None,
        title: str,
        company_name: str,
        location: str | None,
        source_platform: str,
    ) -> str:
        if source_url:
            normalized_url = source_url.strip().split("?")[0].split("#")[0].casefold()
            base = f"u:{user_id}|url:{normalized_url}"
        else:
            normalized_title = (title or "").casefold().strip()
            normalized_company = (company_name or "").casefold().strip()
            normalized_location = (location or "").casefold().strip()
            normalized_platform = str(source_platform).casefold().strip()
            base = f"u:{user_id}|t:{normalized_title}|c:{normalized_company}|l:{normalized_location}|p:{normalized_platform}"
        digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]
        return f"job-{digest}"

    def _normalize(self, text: str) -> str:
        lowered = text.casefold()
        lowered = re.sub(r"[^\w\s/+.-]", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    def _collect_keywords(self, normalized: str, keywords: list[str]) -> list[str]:
        return [keyword for keyword in keywords if keyword in normalized]

    def _extract_years(self, normalized: str) -> float:
        matches = [
            float(value)
            for value in re.findall(r"(\d{1,2})(?:\+)?\s*(?:yıl|year)", normalized)
        ]
        return max(matches) if matches else 0.0

    def _extract_management_years(self, normalized: str) -> float:
        matches = [
            float(value)
            for value in re.findall(
                r"(\d{1,2})(?:\+)?\s*(?:yıl|year).{0,20}(?:lead|manager|yönetim|liderlik)",
                normalized,
            )
        ]
        return max(matches) if matches else 0.0

    def _infer_work_mode(self, normalized: str) -> WorkMode:
        if "remote" in normalized or "uzaktan" in normalized:
            return WorkMode.remote
        if "onsite" in normalized or "office" in normalized or "ofis" in normalized:
            return WorkMode.onsite
        return WorkMode.hybrid

    def _titleize_items(self, items: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in items:
            if item.upper() in {"QA", "CI/CD"}:
                normalized.append(item.upper())
            elif item.lower() == "xray":
                normalized.append("Xray")
            else:
                normalized.append(item.title())
        return normalized
