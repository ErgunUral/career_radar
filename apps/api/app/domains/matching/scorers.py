from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass

from .schemas import (
    CandidateProfileInput,
    JobPostingInput,
    MatchingWeights,
    Recommendation,
)


def _lower_set(values: list[str]) -> set[str]:
    return {value.strip().casefold() for value in values if value.strip()}


def _keyword_overlap(left: list[str], right: list[str]) -> float:
    left_set = _lower_set(left)
    right_set = _lower_set(right)
    if not left_set or not right_set:
        return 0.0
    intersection = len(left_set & right_set)
    union = len(left_set | right_set)
    return intersection / union if union else 0.0


def _normalize_language(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    aliases = {
        "english": "english",
        "ingilizce": "english",
        "turkish": "turkish",
        "turkce": "turkish",
        "german": "german",
        "almanca": "german",
    }
    return aliases.get(normalized, normalized)


@dataclass
class RuleScoreBreakdown:
    title: float
    experience: float
    technical_skills: float
    leadership: float
    industry: float
    location_and_work_mode: float
    language: float
    education_and_certificates: float
    salary_and_benefits: float


class RuleBasedScorer:
    def score(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> RuleScoreBreakdown:
        title = self._score_title(candidate, job)
        experience = self._score_experience(candidate, job)
        technical = self._score_technical_skills(candidate, job)
        leadership = self._score_leadership(candidate, job)
        industry = self._score_industry(candidate, job)
        location_work_mode = self._score_location_work_mode(candidate, job)
        language = self._score_language(candidate, job)
        education_certificates = self._score_education_and_certificates(candidate, job)
        salary = self._score_salary(candidate, job)
        return RuleScoreBreakdown(
            title=title,
            experience=experience,
            technical_skills=technical,
            leadership=leadership,
            industry=industry,
            location_and_work_mode=location_work_mode,
            language=language,
            education_and_certificates=education_certificates,
            salary_and_benefits=salary,
        )

    def weighted_score(
        self, breakdown: RuleScoreBreakdown, weights: MatchingWeights
    ) -> float:
        normalized = weights.normalized()
        raw_scores = asdict(breakdown)
        total = sum(raw_scores[key] * normalized[key] for key in raw_scores)
        return round(total * 100.0, 2)

    def _score_title(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        candidate_title = candidate.headline.casefold()
        job_title = job.title.casefold()
        if candidate_title == job_title:
            return 1.0
        if candidate_title in job_title or job_title in candidate_title:
            return 0.9
        candidate_tokens = candidate_title.split()
        job_tokens = job_title.split()
        return round(_keyword_overlap(candidate_tokens, job_tokens), 4)

    def _score_experience(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        if job.min_years_experience == 0:
            return 1.0
        ratio = candidate.total_experience_years / max(job.min_years_experience, 0.5)
        return round(min(ratio, 1.2) / 1.2, 4)

    def _score_technical_skills(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        required = _lower_set(job.required_skills)
        preferred = _lower_set(job.preferred_skills)
        candidate_skills = _lower_set(candidate.skills)
        if not required and not preferred:
            return 1.0
        required_score = (
            len(required & candidate_skills) / len(required) if required else 1.0
        )
        preferred_score = (
            len(preferred & candidate_skills) / len(preferred) if preferred else 1.0
        )
        return round((required_score * 0.75) + (preferred_score * 0.25), 4)

    def _score_leadership(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        if job.management_years_required == 0 and candidate.management_years == 0:
            return 1.0
        if job.management_years_required == 0:
            return 0.85 if candidate.management_years > 0 else 0.5
        year_score = min(
            candidate.management_years / max(job.management_years_required, 0.5), 1.0
        )
        team_bonus = 0.15 if candidate.team_size_managed >= 5 else 0.0
        return round(min(year_score + team_bonus, 1.0), 4)

    def _score_industry(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        if not job.industries:
            return 1.0
        return round(_keyword_overlap(candidate.industries, job.industries), 4)

    def _score_location_work_mode(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        preferred_locations = _lower_set(candidate.preferred_locations)
        work_modes = {mode.value for mode in candidate.work_modes}
        location_score = (
            1.0
            if not preferred_locations
            else float(job.location.casefold() in preferred_locations)
        )
        work_mode_score = (
            1.0 if not work_modes else float(job.work_mode.value in work_modes)
        )
        return round((location_score * 0.5) + (work_mode_score * 0.5), 4)

    def _score_language(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        if not job.language_requirement:
            return 1.0
        candidate_languages = {
            _normalize_language(language) for language in candidate.languages
        }
        job_language = _normalize_language(job.language_requirement)
        return 1.0 if job_language in candidate_languages else 0.0

    def _score_education_and_certificates(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        education_score = (
            _keyword_overlap(candidate.educations, job.education_requirements)
            if job.education_requirements
            else 1.0
        )
        certificate_score = (
            _keyword_overlap(candidate.certifications, job.certification_requirements)
            if job.certification_requirements
            else 1.0
        )
        return round((education_score * 0.6) + (certificate_score * 0.4), 4)

    def _score_salary(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> float:
        if candidate.salary_expectation is None or job.salary_max is None:
            return 0.5
        if candidate.salary_expectation <= job.salary_max:
            return 1.0
        if job.salary_min and candidate.salary_expectation <= job.salary_max * 1.1:
            return 0.7
        return 0.0


def derive_recommendation(
    total_score: float, semantic_similarity: float, gaps: list[str]
) -> tuple[Recommendation, str]:
    if total_score >= 85 and semantic_similarity >= 0.75:
        return (
            Recommendation.apply_now,
            "Kural tabanlı skor ve anlamsal yakınlık birlikte çok güçlü.",
        )
    if total_score >= 75 and semantic_similarity >= 0.5:
        return (
            Recommendation.high_priority,
            "Profil ve ilan gereksinimleri yüksek ölçüde örtüşüyor.",
        )
    if any("lokasyon" in gap.casefold() for gap in gaps):
        return (
            Recommendation.location_mismatch,
            "Temel yetkinlik uyumu olsa da lokasyon/çalışma modeli uyumsuzluğu var.",
        )
    if any("maaş" in gap.casefold() for gap in gaps):
        return (
            Recommendation.salary_mismatch,
            "Maaş beklentisi mevcut ilan aralığı ile örtüşmüyor.",
        )
    if total_score >= 60:
        return (
            Recommendation.worth_reviewing,
            "İlan değerlendirilebilir; başvuru öncesi hedefli özelleştirme önerilir.",
        )
    if total_score >= 45:
        return (
            Recommendation.skill_gap,
            "Başvuru yapılabilir ancak yetkinlik boşlukları belirgin.",
        )
    return (
        Recommendation.do_not_apply,
        "Kritik gereksinimler ve anlamsal yakınlık zayıf olduğu için öncelik düşük.",
    )
