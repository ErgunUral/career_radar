from __future__ import annotations

import random
import time

from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[2] / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.config import Settings
from app.domains.matching.schemas import CandidateProfileInput, JobPostingInput, MatchRequest, WorkMode
from app.domains.matching.service import HybridMatchingService


def build_candidate() -> CandidateProfileInput:
    return CandidateProfileInput(
        candidate_id="bench-candidate",
        headline="QA Manager",
        summary="Fintech kalite yonetimi, test otomasyonu, CI/CD ve liderlik",
        total_experience_years=14,
        management_years=7,
        team_size_managed=20,
        skills=["Python", "CI/CD", "Jira", "Xray", "Selenium", "Cypress", "API Testing"],
        industries=["Fintech", "E-commerce"],
        languages=["Türkçe", "İngilizce"],
        certifications=["ISTQB"],
        educations=["Computer Engineering"],
        preferred_locations=["remote"],
        work_modes=[WorkMode.remote, WorkMode.hybrid],
        salary_expectation=180000,
    )


def build_jobs(count: int) -> list[JobPostingInput]:
    templates = [
        ("Software Test Manager", ["Python", "Jira", "CI/CD"], ["Fintech"], WorkMode.remote),
        ("QA Lead", ["Selenium", "Regression Testing"], ["E-commerce"], WorkMode.hybrid),
        ("Quality Engineering Manager", ["API Testing", "Xray", "Cypress"], ["Fintech"], WorkMode.remote),
    ]
    jobs: list[JobPostingInput] = []
    for index in range(count):
        title, skills, industries, work_mode = random.choice(templates)
        jobs.append(
            JobPostingInput(
                job_id=f"job-{index}",
                title=title,
                description=f"{title} rolü için {', '.join(skills)} deneyimi aranıyor.",
                requirements=", ".join(skills),
                required_skills=skills,
                preferred_skills=["Leadership", "Agile"],
                industries=industries,
                min_years_experience=random.choice([6, 8, 10, 12]),
                management_years_required=random.choice([2, 4, 5]),
                location="remote",
                work_mode=work_mode,
                language_requirement="İngilizce",
                salary_max=random.choice([160000, 180000, 210000]),
            )
        )
    return jobs


def run_benchmark(job_count: int = 5000) -> None:
    service = HybridMatchingService(Settings(prefilter_limit=1500))
    request = MatchRequest(candidate=build_candidate(), jobs=build_jobs(job_count), top_k=25, semantic_prefilter_limit=1500)
    started_at = time.perf_counter()
    response = service.match_jobs(request)
    duration = time.perf_counter() - started_at
    throughput = job_count / duration if duration else 0.0

    print(f"Toplam ilan: {job_count}")
    print(f"Süre: {duration:.3f} saniye")
    print(f"İşlem hızı: {throughput:.2f} eşleştirme/sn")
    print(f"En iyi skor: {response.results[0].total_score:.2f}")


if __name__ == "__main__":
    run_benchmark()
