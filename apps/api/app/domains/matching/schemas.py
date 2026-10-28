from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class WorkMode(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"


class Recommendation(str, Enum):
    apply_now = "Hemen başvur"
    high_priority = "Yüksek öncelikli"
    worth_reviewing = "Değerlendirilebilir"
    skill_gap = "Yetkinlik eksiği var"
    below_level = "Deneyim seviyesinin altında"
    above_level = "Deneyim seviyesinin üstünde"
    location_mismatch = "Lokasyon nedeniyle uygun değil"
    salary_mismatch = "Maaş beklentisine uygun değil"
    do_not_apply = "Başvurma"


class MatchingWeights(BaseModel):
    title: float = 15.0
    experience: float = 15.0
    technical_skills: float = 20.0
    leadership: float = 15.0
    industry: float = 10.0
    location_and_work_mode: float = 10.0
    language: float = 5.0
    education_and_certificates: float = 5.0
    salary_and_benefits: float = 5.0

    @property
    def total(self) -> float:
        return sum(self.model_dump().values())

    def normalized(self) -> dict[str, float]:
        total = self.total or 1.0
        return {key: value / total for key, value in self.model_dump().items()}


class PrivacySettings(BaseModel):
    contains_sensitive_data: bool = False
    mask_pii_for_llm: bool = True
    consent_for_processing: bool = True
    allow_federated_processing_only: bool = False


class CandidateProfileInput(BaseModel):
    candidate_id: str | None = None
    headline: str
    summary: str = ""
    total_experience_years: float = Field(default=0.0, ge=0.0, le=60.0)
    management_years: float = Field(default=0.0, ge=0.0, le=60.0)
    team_size_managed: int = Field(default=0, ge=0, le=5000)
    skills: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    educations: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_modes: list[WorkMode] = Field(default_factory=list)
    salary_expectation: float | None = Field(default=None, ge=0)
    raw_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobPostingInput(BaseModel):
    job_id: str
    title: str
    description: str = ""
    requirements: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    min_years_experience: float = Field(default=0.0, ge=0.0, le=60.0)
    management_years_required: float = Field(default=0.0, ge=0.0, le=60.0)
    location: str = ""
    work_mode: WorkMode = WorkMode.hybrid
    language_requirement: str = "Türkçe"
    salary_max: float | None = Field(default=None, ge=0)
    salary_min: float | None = Field(default=None, ge=0)
    education_requirements: list[str] = Field(default_factory=list)
    certification_requirements: list[str] = Field(default_factory=list)
    raw_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MatchRequest(BaseModel):
    candidate: CandidateProfileInput
    jobs: list[JobPostingInput]
    weights: MatchingWeights = Field(default_factory=MatchingWeights)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    top_k: int = Field(default=10, ge=1, le=100)
    semantic_prefilter_limit: int | None = Field(default=None, ge=10, le=10000)

    @model_validator(mode="after")
    def validate_consent(self) -> MatchRequest:
        if (
            self.privacy.contains_sensitive_data
            and not self.privacy.consent_for_processing
        ):
            raise ValueError("Hassas veri işleme için açık rıza gereklidir.")
        return self


class PreprocessSample(BaseModel):
    text: str = ""
    numeric_features: dict[str, float | None] = Field(default_factory=dict)
    categorical_features: dict[str, str | None] = Field(default_factory=dict)


class PreprocessRequest(BaseModel):
    samples: list[PreprocessSample]


class StructuredFeatureSummary(BaseModel):
    imputed_values: dict[str, float]
    clipped_outliers: dict[str, int]
    categorical_vocabularies: dict[str, list[str]]


class PreprocessResponse(BaseModel):
    normalized_texts: list[str]
    cleaned_tokens: list[list[str]]
    numeric_features: list[dict[str, float]]
    categorical_features: list[dict[str, str]]
    summary: StructuredFeatureSummary


class ScoreBreakdown(BaseModel):
    title: float
    experience: float
    technical_skills: float
    leadership: float
    industry: float
    location_and_work_mode: float
    language: float
    education_and_certificates: float
    salary_and_benefits: float
    semantic_alignment: float


class MatchResult(BaseModel):
    job_id: str
    total_score: float
    recommendation: Recommendation
    recommendation_reason: str
    semantic_similarity: float
    breakdown: ScoreBreakdown
    strengths: list[str]
    gaps: list[str]
    matched_keywords: list[str]
    missing_keywords: list[str]
    privacy_notes: list[str]


class MatchResponse(BaseModel):
    candidate_id: str | None
    engine_version: str
    results: list[MatchResult]


class EvaluationRecord(BaseModel):
    predicted_positive: bool
    actual_positive: bool


class EvaluationSummary(BaseModel):
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    false_negative_rate: float
