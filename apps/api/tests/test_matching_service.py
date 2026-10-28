from app.core.config import Settings
from app.domains.matching.evaluation import evaluate_predictions
from app.domains.matching.schemas import (
    CandidateProfileInput,
    EvaluationRecord,
    JobPostingInput,
    MatchRequest,
    WorkMode,
)
from app.domains.matching.service import HybridMatchingService


def build_candidate() -> CandidateProfileInput:
    return CandidateProfileInput(
        candidate_id="cand-1",
        headline="QA Manager",
        summary="Fintech ve e-ticaret alanlarında test otomasyonu, kalite stratejisi ve ekip yönetimi deneyimi.",
        total_experience_years=14,
        management_years=7,
        team_size_managed=18,
        skills=[
            "Python",
            "Selenium",
            "Cypress",
            "CI/CD",
            "Jira",
            "Xray",
            "API Testing",
        ],
        industries=["Fintech", "E-commerce"],
        languages=["Türkçe", "İngilizce"],
        certifications=["ISTQB"],
        educations=["Computer Engineering"],
        preferred_locations=["istanbul", "remote"],
        work_modes=[WorkMode.remote, WorkMode.hybrid],
        salary_expectation=180000,
    )


def build_jobs() -> list[JobPostingInput]:
    return [
        JobPostingInput(
            job_id="job-strong",
            title="Software Test Manager",
            description="Fintech odakli kalite yonetimi, test otomasyonu ve liderlik.",
            requirements="CI/CD, Jira, Xray, API testing, test strategy, leadership",
            required_skills=["Python", "CI/CD", "Jira", "Xray", "API Testing"],
            preferred_skills=["Selenium", "Cypress"],
            industries=["Fintech"],
            min_years_experience=10,
            management_years_required=5,
            location="remote",
            work_mode=WorkMode.remote,
            language_requirement="İngilizce",
            salary_max=220000,
            certification_requirements=["ISTQB"],
        ),
        JobPostingInput(
            job_id="job-medium",
            title="QA Lead",
            description="E-ticaret tecrubesi tercih edilir, manuel ve otomasyon test liderligi.",
            requirements="Jira, regression testing",
            required_skills=["Jira", "Regression Testing"],
            preferred_skills=["SQL"],
            industries=["E-commerce"],
            min_years_experience=6,
            management_years_required=2,
            location="istanbul",
            work_mode=WorkMode.hybrid,
            language_requirement="Türkçe",
            salary_max=170000,
        ),
        JobPostingInput(
            job_id="job-weak",
            title="Junior Mobile QA",
            description="Yeni mezun veya 1-2 yil deneyimli aday.",
            requirements="Appium, mobile testing",
            required_skills=["Appium"],
            industries=["Gaming"],
            min_years_experience=2,
            management_years_required=0,
            location="ankara",
            work_mode=WorkMode.onsite,
            language_requirement="Türkçe",
            salary_max=70000,
        ),
    ]


def test_matching_service_ranks_best_job_first() -> None:
    service = HybridMatchingService(Settings())
    response = service.match_jobs(
        MatchRequest(candidate=build_candidate(), jobs=build_jobs(), top_k=3)
    )

    assert response.results[0].job_id == "job-strong"
    assert response.results[0].total_score > response.results[1].total_score
    assert (
        response.results[0].semantic_similarity
        >= response.results[1].semantic_similarity
    )
    assert response.results[0].recommendation.value in {
        "Hemen başvur",
        "Yüksek öncelikli",
    }


def test_evaluation_summary_meets_target_on_curated_fixture() -> None:
    records = [
        EvaluationRecord(predicted_positive=True, actual_positive=True)
        for _ in range(49)
    ]
    records.extend(
        EvaluationRecord(predicted_positive=False, actual_positive=False)
        for _ in range(49)
    )
    records.append(EvaluationRecord(predicted_positive=False, actual_positive=True))
    records.append(EvaluationRecord(predicted_positive=True, actual_positive=False))

    summary = evaluate_predictions(records)

    assert summary.f1_score >= 0.95
    assert summary.false_positive_rate <= 0.03
    assert summary.false_negative_rate <= 0.02
