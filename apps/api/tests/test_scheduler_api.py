from fastapi.testclient import TestClient

from app.domains.jobs.schemas import JobSourcePlatform
from app.domains.matching.schemas import WorkMode
from app.domains.watchers.discovery import LiveJobDiscoveryService
from app.domains.watchers.schemas import DiscoveredJobInput, DiscoverySourceReport
from app.main import app

client = TestClient(app)


def watcher_payload() -> dict:
    return {
        "user_id": "user-sched-1",
        "query_name": "Scheduler QA Manager Watcher",
        "source_platform": "linkedin_search_url",
        "search_criteria": {
            "keywords": ["qa", "test", "manager"],
            "locations": ["remote"],
            "industries": ["fintech"],
            "work_modes": ["remote"],
            "min_experience_years": 8,
            "position_types": ["full-time"],
        },
        "candidate_profile": {
            "candidate_id": "cand-sched-1",
            "headline": "QA Manager",
            "summary": "Fintech test otomasyonu ve liderlik deneyimi",
            "total_experience_years": 13,
            "management_years": 6,
            "team_size_managed": 10,
            "skills": ["Python", "Jira", "Xray", "CI/CD", "Selenium"],
            "industries": ["Fintech"],
            "languages": ["Türkçe", "İngilizce"],
            "certifications": ["ISTQB"],
            "educations": ["Computer Engineering"],
            "preferred_locations": ["remote"],
            "work_modes": ["remote"],
            "salary_expectation": 160000,
        },
        "minimum_match_score": 70,
        "sync_frequency_minutes": 120,
        "notification_channels": ["in_app"],
        "metadata": {
            "source_urls": [
                "https://boards-api.greenhouse.io/v1/boards/example-sched/jobs"
            ]
        },
    }


def test_scheduler_status_endpoint_reports_interval_and_disabled_in_tests() -> None:
    response = client.get("/api/v1/scheduler/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["interval_minutes"] == 120
    assert payload["max_jobs_per_run"] == 10
    assert payload["enabled"] is False


def test_scheduler_start_stop_and_status_reflect_state(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.core.scheduler import watcher_scheduler

    new_settings = _build_settings(scheduler_enabled=True)
    monkeypatch.setattr("app.core.scheduler.get_settings", lambda: new_settings)
    get_settings.cache_clear()
    watcher_scheduler.settings = new_settings
    try:
        start = client.post("/api/v1/scheduler/start")
        assert start.status_code == 200
        first = start.json()
        assert first["status"] in {"started", "already_running"}
        assert first["interval_minutes"] == 120

        status = client.get("/api/v1/scheduler/status")
        assert status.status_code == 200
        jobs = status.json()["jobs"]
        assert len(jobs) >= 1
        job = jobs[0]
        assert job["id"] == "watcher_sweep"
        assert (
            "interval" in job["trigger"].lower() or "minutes" in job["trigger"].lower()
        )

        stop = client.post("/api/v1/scheduler/stop")
        assert stop.status_code == 200
        assert stop.json()["status"] == "stopped"
    finally:
        client.post("/api/v1/scheduler/stop")


def test_scheduler_run_all_dispatches_active_watchers(monkeypatch) -> None:
    created = client.post("/api/v1/watchers", json=watcher_payload())
    assert created.status_code == 200
    watcher_id = created.json()["id"]

    def fake_discover(_self, source_urls, max_jobs=10):
        assert source_urls == [
            "https://boards-api.greenhouse.io/v1/boards/example-sched/jobs"
        ]
        assert max_jobs == 10
        return (
            [
                DiscoveredJobInput(
                    title="QA Automation Manager",
                    company_name="Scheduler Fintech",
                    source_platform=JobSourcePlatform.company_page,
                    source_url="https://careers.example-sched.com/jobs/qa-automation-manager",
                    location="remote",
                    work_mode=WorkMode.remote,
                    raw_text="Fintech şirketi için QA Automation Manager. 8 yıl deneyim, Python, Jira, Xray, CI/CD ve liderlik deneyimi gerekir.",
                    metadata={"position_type": "full-time", "is_active": True},
                ),
                DiscoveredJobInput(
                    title="Closed QA Role",
                    company_name="Closed Co",
                    source_platform=JobSourcePlatform.company_page,
                    source_url="https://careers.example-sched.com/jobs/closed",
                    location="remote",
                    work_mode=WorkMode.remote,
                    raw_text="Kapalı ilan",
                    metadata={"position_type": "full-time", "is_active": False},
                ),
            ],
            [
                DiscoverySourceReport(
                    source_url="https://boards-api.greenhouse.io/v1/boards/example-sched/jobs",
                    fetched_jobs=2,
                )
            ],
        )

    monkeypatch.setattr(LiveJobDiscoveryService, "discover", fake_discover)

    run_response = client.post("/api/v1/scheduler/run")
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["status"] == "completed"
    summary = body["summary"]
    assert summary["watchers_scanned"] == 1
    assert summary["watchers_with_urls"] == 1
    assert summary["watchers_dispatched"] == 1
    assert summary["watchers_failed"] == 0
    assert summary["processed_jobs_total"] == 1
    assert summary["inactive_jobs_skipped_total"] == 1
    assert summary["per_watcher"][0]["watcher_id"] == watcher_id
    assert summary["per_watcher"][0]["status"] == "completed"

    jobs = client.get("/api/v1/jobs", params={"user_id": "user-sched-1"})
    assert jobs.status_code == 200
    imported = jobs.json()
    assert len(imported) == 1
    assert imported[0]["company_name"] == "Scheduler Fintech"
    assert imported[0]["metadata"]["discovered_live"] is True


def test_scheduler_run_single_watcher_endpoint(monkeypatch) -> None:
    created = client.post("/api/v1/watchers", json=watcher_payload())
    watcher_id = created.json()["id"]

    def fake_discover(_self, source_urls, max_jobs=10):
        return (
            [
                DiscoveredJobInput(
                    title="Senior SDET",
                    company_name="Single Scheduler Co",
                    source_platform=JobSourcePlatform.company_page,
                    source_url="https://careers.example-single/jobs/sdet",
                    location="remote",
                    work_mode=WorkMode.remote,
                    raw_text="Senior SDET rolü: Python, Selenium, CI/CD.",
                    metadata={"position_type": "full-time", "is_active": True},
                )
            ],
            [
                DiscoverySourceReport(
                    source_url="https://boards-api.greenhouse.io/v1/boards/example-sched/jobs",
                    fetched_jobs=1,
                )
            ],
        )

    monkeypatch.setattr(LiveJobDiscoveryService, "discover", fake_discover)

    response = client.post(f"/api/v1/scheduler/run/{watcher_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["result"]["watcher_id"] == watcher_id
    assert body["result"]["processed_jobs"] == 1
    assert body["result"]["status"] == "completed"


def test_scheduler_run_single_watcher_missing_or_invalid_watcher() -> None:
    missing = client.post("/api/v1/scheduler/run/watcher-nonexistent")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Watcher bulunamadı."

    no_url_payload = watcher_payload()
    no_url_payload["metadata"] = {}
    no_url_payload["user_id"] = "user-sched-no-url"
    created = client.post("/api/v1/watchers", json=no_url_payload)
    no_run = client.post(f"/api/v1/scheduler/run/{created.json()['id']}")
    assert no_run.status_code == 400
    assert "kaynak URL" in no_run.json()["detail"]


def _build_settings(**overrides):
    from app.core.config import Settings

    data = Settings().model_dump()
    data.update(overrides)
    return Settings(**data)
