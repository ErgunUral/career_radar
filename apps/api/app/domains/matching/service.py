from __future__ import annotations

from dataclasses import asdict

from ...core.config import Settings
from .embedding import InMemoryVectorIndex, cosine_similarity, create_embedder
from .preprocessing import StructuredPreprocessor, TextPreprocessor
from .schemas import (
    CandidateProfileInput,
    JobPostingInput,
    MatchRequest,
    MatchResponse,
    MatchResult,
    PreprocessRequest,
    PreprocessResponse,
    ScoreBreakdown,
)
from .scorers import RuleBasedScorer, derive_recommendation


class HybridMatchingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.text_preprocessor = TextPreprocessor()
        self.structured_preprocessor = StructuredPreprocessor()
        self.rule_scorer = RuleBasedScorer()
        self.embedder = create_embedder(
            settings.semantic_model_name, prefer_sentence_transformer=False
        )

    def preprocess_samples(self, request: PreprocessRequest) -> PreprocessResponse:
        return self.structured_preprocessor.preprocess(request)

    def match_jobs(self, request: MatchRequest) -> MatchResponse:
        candidate_text = self.text_preprocessor.compose_candidate_text(
            request.candidate
        )
        job_texts = [
            self.text_preprocessor.compose_job_text(job) for job in request.jobs
        ]

        candidate_embedding = self.embedder.encode([candidate_text])
        job_embeddings = self.embedder.encode(job_texts)
        vector_index = InMemoryVectorIndex(job_embeddings)
        prefilter_limit = request.semantic_prefilter_limit or min(
            len(request.jobs), self.settings.prefilter_limit
        )
        hits = vector_index.query(
            candidate_embedding[0], top_k=min(prefilter_limit, len(request.jobs))
        )
        hit_map = {hit.index: hit.similarity for hit in hits}
        ranked_indices = (
            list(hit_map.keys())
            if len(hit_map) < len(request.jobs)
            else list(range(len(request.jobs)))
        )

        results: list[MatchResult] = []
        for index in ranked_indices:
            job = request.jobs[index]
            semantic_similarity = hit_map.get(index)
            if semantic_similarity is None:
                semantic_similarity = float(
                    cosine_similarity(
                        candidate_embedding, job_embeddings[index : index + 1]
                    )[0][0]
                )
            results.append(
                self._match_single(
                    request.candidate,
                    job,
                    semantic_similarity,
                    request.weights,
                    request.privacy.mask_pii_for_llm,
                )
            )

        sorted_results = sorted(
            results, key=lambda item: item.total_score, reverse=True
        )[: request.top_k]
        return MatchResponse(
            candidate_id=request.candidate.candidate_id,
            engine_version=self.settings.app_version,
            results=sorted_results,
        )

    def _match_single(
        self,
        candidate: CandidateProfileInput,
        job: JobPostingInput,
        semantic_similarity: float,
        weights,
        mask_pii_for_llm: bool,
    ) -> MatchResult:
        breakdown = self.rule_scorer.score(candidate, job)
        rule_score = self.rule_scorer.weighted_score(breakdown, weights)
        hybrid_score = round(
            (rule_score * (1.0 - self.settings.semantic_balance))
            + (semantic_similarity * 100.0 * self.settings.semantic_balance),
            2,
        )

        matched_keywords, missing_keywords = self._extract_keyword_delta(candidate, job)
        strengths = self._build_strengths(
            breakdown, matched_keywords, semantic_similarity
        )
        gaps = self._build_gaps(breakdown, missing_keywords, candidate, job)
        recommendation, reason = derive_recommendation(
            hybrid_score, semantic_similarity, gaps
        )

        privacy_notes = [
            "KVKK/GDPR için veri minimizasyonu uygulanmalı.",
            "PII alanları LLM veya harici servis çağrılarında maskelenmeli."
            if mask_pii_for_llm
            else "PII maskeleme devre dışı bırakıldı.",
            "Federatif öğrenme gereksinimi varsa embedding işlemleri kuruma yakın ortamda çalıştırılmalı.",
        ]

        return MatchResult(
            job_id=job.job_id,
            total_score=hybrid_score,
            recommendation=recommendation,
            recommendation_reason=reason,
            semantic_similarity=round(semantic_similarity, 4),
            breakdown=ScoreBreakdown(
                **asdict(breakdown), semantic_alignment=round(semantic_similarity, 4)
            ),
            strengths=strengths,
            gaps=gaps,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            privacy_notes=privacy_notes,
        )

    def _extract_keyword_delta(
        self, candidate: CandidateProfileInput, job: JobPostingInput
    ) -> tuple[list[str], list[str]]:
        candidate_skills = {value.casefold(): value for value in candidate.skills}
        required = {value.casefold(): value for value in job.required_skills}
        preferred = {value.casefold(): value for value in job.preferred_skills}
        matched = [
            original
            for key, original in {**required, **preferred}.items()
            if key in candidate_skills
        ]
        missing = [
            original
            for key, original in required.items()
            if key not in candidate_skills
        ]
        return sorted(matched), sorted(missing)

    def _build_strengths(
        self, breakdown, matched_keywords: list[str], semantic_similarity: float
    ) -> list[str]:
        strengths: list[str] = []
        if breakdown.technical_skills >= 0.7:
            strengths.append("Teknik yetkinlik eşleşmesi güçlü.")
        if breakdown.leadership >= 0.7:
            strengths.append("Yönetim ve liderlik deneyimi role yakın.")
        if breakdown.industry >= 0.6:
            strengths.append("Sektör deneyimi ilanın bağlamıyla örtüşüyor.")
        if semantic_similarity >= 0.7:
            strengths.append("Profil özeti ile ilan metni anlamsal olarak yakın.")
        if matched_keywords:
            strengths.append(
                f"Eşleşen anahtar kelimeler: {', '.join(matched_keywords[:6])}."
            )
        return strengths or [
            "Profil ile ilan arasında sınırlı ama anlamlı bazı ortak sinyaller var."
        ]

    def _build_gaps(
        self,
        breakdown,
        missing_keywords: list[str],
        candidate: CandidateProfileInput,
        job: JobPostingInput,
    ) -> list[str]:
        gaps: list[str] = []
        if breakdown.experience < 0.6:
            gaps.append("Deneyim yılı beklentisi tam karşılanmıyor.")
        if breakdown.leadership < 0.5 and job.management_years_required > 0:
            gaps.append("Yönetim deneyimi gereksinimi altında kalıyor.")
        if breakdown.location_and_work_mode < 0.5:
            gaps.append("Lokasyon veya çalışma modeli tercihi tam uyuşmuyor.")
        if breakdown.salary_and_benefits < 0.5:
            gaps.append("Maaş beklentisi mevcut aralıkla uyumsuz.")
        if missing_keywords:
            gaps.append(f"Eksik anahtar kelimeler: {', '.join(missing_keywords[:6])}.")
        if breakdown.language < 1.0:
            gaps.append(
                f"Dil gereksinimi ({job.language_requirement}) açık biçimde doğrulanamadı."
            )
        if candidate.management_years > job.management_years_required + 5:
            gaps.append(
                "Rol, mevcut yönetim deneyimine göre daha düşük kıdemli olabilir."
            )
        return gaps
