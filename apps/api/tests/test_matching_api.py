from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/matching/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_batch_match_endpoint_returns_ranked_results() -> None:
    payload = {
        "candidate": {
            "candidate_id": "cand-api",
            "headline": "QA Manager",
            "summary": "Test otomasyonu ve fintech kalite liderligi",
            "total_experience_years": 13,
            "management_years": 6,
            "team_size_managed": 12,
            "skills": ["Python", "Selenium", "CI/CD", "Jira", "Xray"],
            "industries": ["Fintech"],
            "languages": ["Türkçe", "İngilizce"],
            "certifications": ["ISTQB"],
            "educations": ["Computer Engineering"],
            "preferred_locations": ["remote"],
            "work_modes": ["remote"],
            "salary_expectation": 150000,
        },
        "jobs": [
            {
                "job_id": "job-api-1",
                "title": "Test Automation Manager",
                "description": "Fintech, test otomasyonu ve liderlik",
                "requirements": "Python, CI/CD, Jira, Xray",
                "required_skills": ["Python", "CI/CD", "Jira"],
                "preferred_skills": ["Xray"],
                "industries": ["Fintech"],
                "min_years_experience": 8,
                "management_years_required": 4,
                "location": "remote",
                "work_mode": "remote",
                "language_requirement": "İngilizce",
                "salary_max": 180000,
                "certification_requirements": ["ISTQB"],
            }
        ],
        "top_k": 1,
    }

    response = client.post("/api/v1/matching/batch-match", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_id"] == "cand-api"
    assert body["results"][0]["job_id"] == "job-api-1"
    assert body["results"][0]["total_score"] >= 75


def test_preprocess_endpoint_normalizes_payload() -> None:
    payload = {
        "samples": [
            {
                "text": "Yazılım testlerinde, otomasyon araçlarıyla çalıştım.",
                "numeric_features": {"years": 12},
                "categorical_features": {"mode": "remote"},
            }
        ]
    }

    response = client.post("/api/v1/matching/preprocess", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "yazilim" in body["normalized_texts"][0]
    assert "test" in body["cleaned_tokens"][0]
