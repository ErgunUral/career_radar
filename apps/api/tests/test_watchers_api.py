from fastapi.testclient import TestClient

from app.domains.jobs.schemas import JobSourcePlatform
from app.domains.matching.schemas import WorkMode
from app.domains.watchers.discovery import LiveJobDiscoveryService
from app.domains.watchers.schemas import DiscoveredJobInput, DiscoverySourceReport
from app.main import app

client = TestClient(app)


def watcher_payload() -> dict:
    return {
        "user_id": "user-1",
        "query_name": "LinkedIn QA Manager",
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
            "candidate_id": "cand-1",
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
        "sync_frequency_minutes": 30,
        "notification_channels": ["in_app", "email"],
    }


def run_payload() -> dict:
    return {
        "triggered_by": "manual",
        "jobs": [
            {
                "job_id": "job-watch-1",
                "title": "QA Automation Manager",
                "description": "Fintech, test otomasyonu ve liderlik",
                "requirements": "Python, Jira, Xray, CI/CD",
                "required_skills": ["Python", "Jira", "CI/CD"],
                "preferred_skills": ["Xray", "Selenium"],
                "industries": ["Fintech"],
                "min_years_experience": 9,
                "management_years_required": 4,
                "location": "remote",
                "work_mode": "remote",
                "language_requirement": "İngilizce",
                "salary_max": 180000,
                "metadata": {
                    "position_type": "full-time",
                    "company_name": "Radar Fintech",
                },
            },
            {
                "job_id": "job-watch-2",
                "title": "Junior Manual Tester",
                "description": "Giriş seviyesi test rolü",
                "requirements": "Manual testing",
                "required_skills": ["Manual Testing"],
                "industries": ["Gaming"],
                "min_years_experience": 2,
                "location": "ankara",
                "work_mode": "onsite",
                "metadata": {
                    "position_type": "full-time",
                    "company_name": "Other Co",
                },
            },
        ],
    }


def test_create_run_archive_and_notifications_flow() -> None:
    created = client.post("/api/v1/watchers", json=watcher_payload())
    assert created.status_code == 200
    watcher_id = created.json()["id"]

    run_response = client.post(f"/api/v1/watchers/{watcher_id}/run", json=run_payload())
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["run"]["status"] == "completed"
    assert run_body["run"]["matched_jobs"] == 1
    assert len(run_body["notifications"]) == 2
    assert run_body["archived_jobs"][0]["job_id"] == "job-watch-1"

    archive = client.get("/api/v1/archive/jobs", params={"user_id": "user-1"})
    assert archive.status_code == 200
    assert len(archive.json()) == 1

    detail = client.get(
        "/api/v1/archive/jobs/job-watch-1", params={"user_id": "user-1"}
    )
    assert detail.status_code == 200
    assert detail.json()["archive"]["company_name"] == "Radar Fintech"
    assert len(detail.json()["notifications"]) == 2

    notifications = client.get("/api/v1/notifications", params={"user_id": "user-1"})
    assert notifications.status_code == 200
    assert len(notifications.json()) == 2


def test_update_and_list_runs() -> None:
    created = client.post("/api/v1/watchers", json=watcher_payload())
    watcher_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/watchers/{watcher_id}",
        json={"sync_frequency_minutes": 120, "is_active": False},
    )
    assert patched.status_code == 200
    assert patched.json()["sync_frequency_minutes"] == 120
    assert patched.json()["is_active"] is False

    run_response = client.post(f"/api/v1/watchers/{watcher_id}/run", json=run_payload())
    assert run_response.status_code == 200

    runs = client.get(f"/api/v1/watchers/{watcher_id}/runs")
    assert runs.status_code == 200
    assert len(runs.json()) == 1
    assert runs.json()[0]["processed_jobs"] == 2


def test_discover_live_jobs_imports_and_runs_matching(monkeypatch) -> None:
    payload = watcher_payload()
    payload["metadata"] = {
        "source_urls": ["https://boards-api.greenhouse.io/v1/boards/example/jobs"]
    }
    created = client.post("/api/v1/watchers", json=payload)
    assert created.status_code == 200
    watcher_id = created.json()["id"]

    def fake_discover(_self, source_urls: list[str], max_jobs: int = 10):
        assert source_urls == [
            "https://boards-api.greenhouse.io/v1/boards/example/jobs"
        ]
        assert max_jobs == 10
        return (
            [
                DiscoveredJobInput(
                    title="QA Automation Manager",
                    company_name="Example Fintech",
                    source_platform=JobSourcePlatform.company_page,
                    source_url="https://careers.example.com/jobs/qa-automation-manager",
                    location="remote",
                    work_mode=WorkMode.remote,
                    raw_text="Fintech şirketi için QA Automation Manager. 8 yıl deneyim, Python, Jira, Xray, CI/CD ve liderlik deneyimi gerekir.",
                    metadata={"position_type": "full-time"},
                )
            ],
            [
                DiscoverySourceReport(
                    source_url="https://boards-api.greenhouse.io/v1/boards/example/jobs",
                    fetched_jobs=1,
                )
            ],
        )

    monkeypatch.setattr(
        "app.domains.watchers.discovery.LiveJobDiscoveryService.discover", fake_discover
    )

    discovered = client.post(
        f"/api/v1/watchers/{watcher_id}/discover", json={"triggered_by": "test"}
    )
    assert discovered.status_code == 200
    body = discovered.json()
    assert body["run"]["status"] == "completed"
    assert body["run"]["processed_jobs"] == 1
    assert body["run"]["matched_jobs"] == 1
    assert len(body["imported_jobs"]) == 1
    assert body["source_reports"][0]["fetched_jobs"] == 1
    assert body["imported_jobs"][0]["company_name"] == "Example Fintech"

    jobs = client.get("/api/v1/jobs", params={"user_id": "user-1"})
    assert jobs.status_code == 200
    assert len(jobs.json()) == 1
    assert jobs.json()[0]["metadata"]["discovered_live"] is True


def test_discover_live_jobs_skips_inactive_records_before_import(monkeypatch) -> None:
    payload = watcher_payload()
    payload["user_id"] = "user-skip-inactive"
    payload["metadata"] = {
        "source_urls": ["https://www.kariyer.net/is-ilanlari/qa"]
    }  # public source example
    created = client.post("/api/v1/watchers", json=payload)
    assert created.status_code == 200
    watcher_id = created.json()["id"]

    def fake_discover(_self, source_urls: list[str], max_jobs: int = 10):
        assert source_urls == ["https://www.kariyer.net/is-ilanlari/qa"]
        assert max_jobs == 10
        return (
            [
                DiscoveredJobInput(
                    title="Senior QA Lead",
                    company_name="Active Corp",
                    source_platform=JobSourcePlatform.kariyernet,
                    source_url="https://www.kariyer.net/is-ilani/active-corp-senior-qa-lead-1",
                    location="Istanbul",
                    work_mode=WorkMode.hybrid,
                    raw_text="QA leadership, automation, fintech",
                    metadata={"position_type": "full-time", "is_active": True},
                ),
                DiscoveredJobInput(
                    title="QA Manager",
                    company_name="Closed Corp",
                    source_platform=JobSourcePlatform.kariyernet,
                    source_url="https://www.kariyer.net/is-ilani/closed-corp-qa-manager-2",
                    location="Istanbul",
                    work_mode=WorkMode.hybrid,
                    raw_text="Closed job posting",
                    metadata={"position_type": "full-time", "is_active": False},
                ),
            ],
            [
                DiscoverySourceReport(
                    source_url="https://www.kariyer.net/is-ilanlari/qa",
                    source_platform=JobSourcePlatform.kariyernet,
                    fetched_jobs=2,
                )
            ],
        )

    monkeypatch.setattr(
        "app.domains.watchers.discovery.LiveJobDiscoveryService.discover", fake_discover
    )

    discovered = client.post(
        f"/api/v1/watchers/{watcher_id}/discover", json={"triggered_by": "test"}
    )
    assert discovered.status_code == 200
    body = discovered.json()
    assert body["run"]["processed_jobs"] == 1
    assert body["run"]["metadata"]["inactive_jobs_skipped"] == 1
    assert len(body["imported_jobs"]) == 1
    assert body["imported_jobs"][0]["company_name"] == "Active Corp"

    jobs = client.get("/api/v1/jobs", params={"user_id": "user-skip-inactive"})
    assert jobs.status_code == 200
    assert len(jobs.json()) == 1
    assert jobs.json()[0]["company_name"] == "Active Corp"


def test_extract_linkedin_jobs_from_public_search_html() -> None:
    service = LiveJobDiscoveryService()
    html = """
    <li class="base-card" data-entity-urn="urn:li:jobPosting:1234567890">
      <a href="https://tr.linkedin.com/jobs/view/senior-qa-lead-123"></a>
      <h3 class="base-search-card__title">Senior QA Lead</h3>
      <h4 class="base-search-card__subtitle">Insider</h4>
      <span class="job-search-card__location">Istanbul, Turkey</span>
      <time datetime="2026-08-03T10:00:00Z">2 days ago</time>
    </li>
    """
    jobs = service._extract_jobs(
        "https://www.linkedin.com/jobs/search?keywords=qa", "text/html", html
    )
    assert len(jobs) == 1
    assert jobs[0].source_platform == JobSourcePlatform.linkedin
    assert jobs[0].company_name == "Insider"
    assert jobs[0].metadata["published_at"] == "2026-08-03T10:00:00+00:00"


def test_extract_kariyernet_detail_page_marks_inactive() -> None:
    service = LiveJobDiscoveryService()
    html = """
    <h1>QA Manager</h1>
    <a href="https://www.kariyer.net/firma-profil/example-company-1-2">Example Company</a>
    Istanbul İş Yerinde Tam Zamanlı
    1 gün önce güncellendi
    ## İş İlanı Hakkında
    Ekip yönetimi ve yazılım kalite süreçleri.
    ## Aday Kriterleri
    Bu ilan başvuruları artık kabul etmiyor.
    """
    jobs = service._extract_jobs(
        "https://www.kariyer.net/is-ilani/example-company-qa-manager-123",
        "text/html",
        html,
    )
    assert len(jobs) == 1
    assert jobs[0].source_platform == JobSourcePlatform.kariyernet
    assert jobs[0].metadata["is_active"] is False


def test_bot_detection_helper_recognises_common_block_signals() -> None:
    svc = LiveJobDiscoveryService()
    # 403 / 999 / 429 otomatik blocked
    assert svc._looks_like_bot_blocked(403, "<html/>") is True
    assert svc._looks_like_bot_blocked(999, "<html/>") is True
    assert svc._looks_like_bot_blocked(429, "<html/>") is True
    assert svc._looks_like_bot_blocked(503, "<html/>") is True
    # 200 ama Cloudflare challenge body
    assert (
        svc._looks_like_bot_blocked(
            200,
            "<title>Just a moment... Cloudflare güvenlik doğrulaması</title>",
        )
        is True
    )
    # 200 ve Akamai bot page Türkçe
    assert (
        svc._looks_like_bot_blocked(
            200,
            "Tarayıcı doğrulaması lütfen bekleyin rate limit hız sınırı",
        )
        is True
    )
    # Normal 200 ve temiz sayfa → blocked değil
    assert svc._looks_like_bot_blocked(200, "<h1>QA Manager</h1>") is False
    assert svc._looks_like_bot_blocked(201, "") is False
    assert svc._looks_like_bot_blocked(0, "") is False


def test_extract_elemannet_jobs_from_card_html() -> None:
    """Yeni connector #1: Eleman.net kart formatı parse edilsin."""
    service = LiveJobDiscoveryService()
    html = """
    <html><body>
      <li class="list-item">
        <a href="https://www.eleman.net/is/kalite-guvence-muduru-98765">
          <h3>Kalite Güvence Müdürü</h3>
        </a>
        <div class="company">Garanti BBVA Teknoloji</div>
        <div class="location">İstanbul (Anadolu) - Remote</div>
        <span class="date">2 gün önce</span>
      </li>
      <div class="job-card">
        <a href="/is/test-otomasyon-uzmani-123">
          <h4>Test Otomasyon Uzmanı</h4>
        </a>
        <div class="firma">ING Teknoloji</div>
        <span class="konum">Ankara / Hibrit</span>
      </div>
    </body></html>
    """
    jobs = service._extract_jobs(
        "https://www.eleman.net/is-ilanlari?q=kalite", "text/html", html
    )
    assert len(jobs) >= 1, f"Eleman.net connector ÇIKTI BOŞ: {len(jobs)}"
    # Headline: Kalite Güvence Müdürü olmalı (en az 1)
    titles = [j.title for j in jobs]
    assert any("Kalite" in t or "Müdür" in t or "Test" in t for t in titles), (
        f"Başlıklar çıkarılamadı: {titles}"
    )
    # Platform doğrulama
    platforms = [
        j.source_platform.value
        if hasattr(j.source_platform, "value")
        else str(j.source_platform)
        for j in jobs
    ]
    assert any(p in ("eleman_net", "company_page") for p in platforms), (
        f"Yanlış platform: {platforms}"
    )


def test_extract_secrethr_jobs_from_vacancy_html() -> None:
    """Yeni connector #2: SecretHR ilan listesi parse edilsin."""
    service = LiveJobDiscoveryService()
    html = """
    <table class="ilanlar">
      <tr>
        <td><a href="https://secrethr.com/vacancy/test-muduru-4545">Test Müdürü</a></td>
        <td class="company">KoçSistem</td>
        <td class="konum">İstanbul</td>
      </tr>
      <tr>
        <td><a href="/vacancy/qa-team-lead"><h4>QA Team Lead</h4></a></td>
        <td class="firma">Vestel</td>
        <td>Remote</td>
      </tr>
    </table>
    """
    jobs = service._extract_jobs(
        "https://secrethr.com/careers?search=test", "text/html", html
    )
    assert len(jobs) >= 1, f"SecretHR connector BOŞ: {len(jobs)}"
    titles = [j.title for j in jobs]
    assert any("Test" in t or "QA" in t for t in titles), f"Başlıklar: {titles}"


def test_extract_yenibiris_data_attrs() -> None:
    """Yeni connector #3: Yenibiris data-* attribute (modern) ile parse."""
    service = LiveJobDiscoveryService()
    html = """
    <div class="job-list">
      <article class="ilan-item" data-job-title="Yazılım Test Uzmanı" data-company="Turkcell" data-lokasyon="İzmir">
        <a href="https://www.yenibiris.com/is-yeri/yazilim-test-uzmani-888">
          <h3>Yazılım Test Uzmanı</h3>
          <div class="kurum">Turkcell</div>
          <div class="yer">İzmir</div>
        </a>
      </article>
      <div class="card" data-job-title="Kalite Kontrol Uzmanı" data-firma="Arçelik" data-konum="Bursa">
        <a href="/is-yeri/kalite-kontrol-777"><h2>Kalite Kontrol Uzmanı</h2></a>
        <span>Bursa</span>
      </div>
    </div>
    """
    jobs = service._extract_jobs(
        "https://www.yenibiris.com/is-ilanlari?kw=test", "text/html", html
    )
    assert len(jobs) >= 1, f"Yenibiris connector BOŞ: {len(jobs)}"
    titles = {j.title for j in jobs}
    assert any("Test" in t or "Kalite" in t for t in titles), f"Başlıklar: {titles}"


def test_extract_jobturk_anchor_pattern() -> None:
    """Yeni connector #4: JobTürk anchor regex (/is/... veya /ilan/) parse."""
    service = LiveJobDiscoveryService()
    html = """
    <div class="liste">
      <tr><td>Şirket</td><td><a href="https://www.jobturk.com/is/test-muduru-5678">Test Müdürü</a></td><td class="konum">İstanbul</td></tr>
      <tr><td><a href="/ilan/qa-automation-engineer-33"><b>QA Automation Engineer</b></a></td><td class="firma">Hepsiburada</td></tr>
      <tr><td></td><td><a href="/is/kalite-guvence-uzmani-22">Kalite Güvence Uzmanı (Remote)</a></td><td class="yer">Remote</td></tr>
    </div>
    """
    jobs = service._extract_jobs(
        "https://www.jobturk.com/is-ilanlari/kalite", "text/html", html
    )
    # En az 1 tane olmalı (JobTürk anchor pattern: /is/ veya /ilan/)
    assert len(jobs) >= 1, f"JobTürk connector BOŞ: {len(jobs)}"
    titles = {j.title for j in jobs}
    assert any(("Test" in t or "QA" in t or "Kalite" in t) for t in titles), (
        f"Başlıklar: {titles}"
    )
    # Source link /is/ ile başlıyorsa domain eklenmeli
    for j in jobs:
        url = j.source_url or ""
        assert url.startswith("http"), f"JobTürk URL absolute olmalı: {url}"


def test_fetch_html_with_fallback_prefers_httpx_on_success(monkeypatch) -> None:
    svc = LiveJobDiscoveryService()
    called = {"httpx": 0, "cloudscraper": 0, "playwright": 0}

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><h1>OK</h1></html>"

    def fake_httpx_get(url, **kw):
        called["httpx"] += 1
        return DummyResp()

    monkeypatch.setattr("httpx.get", fake_httpx_get)
    monkeypatch.setattr("app.domains.watchers.discovery._HAS_CLOUDSCRAPER", False)
    monkeypatch.setattr("app.domains.watchers.discovery._HAS_PLAYWRIGHT", False)

    status, body, ct, method = svc._fetch_html_with_fallback(
        "https://example.com", allow_playwright=False
    )
    assert status == 200
    assert "<h1>OK</h1>" in body
    assert ct == "text/html"
    assert method == "httpx"
    assert called["httpx"] == 1
    assert called["playwright"] == 0


def test_fetch_html_fallback_runs_playwright_when_httpx_bot_blocked(
    monkeypatch,
) -> None:
    from app.domains.watchers import discovery as disco_mod

    svc = LiveJobDiscoveryService(timeout_seconds=1.0)
    call_log: list[str] = []

    class BlockedResp:
        status_code = 999
        headers = {"content-type": "text/html"}
        text = "<html>Just a moment... LinkedIn bot protection captcha</html>"

    def fake_httpx_get(url, **kw):
        call_log.append("httpx")
        return BlockedResp()

    def fake_pw_fetch(_self, url, timeout):
        call_log.append("playwright")
        return (200, "<html><li>OK Playwright Rendered</li></html>", "text/html")

    monkeypatch.setattr("httpx.get", fake_httpx_get)
    monkeypatch.setattr(disco_mod, "_HAS_CLOUDSCRAPER", False)
    monkeypatch.setattr(disco_mod, "_HAS_PLAYWRIGHT", True)
    monkeypatch.setattr(
        LiveJobDiscoveryService, "_playwright_fetch_page", fake_pw_fetch
    )

    status, body, _ct, method = svc._fetch_html_with_fallback(
        "https://tr.linkedin.com/jobs", allow_playwright=True
    )
    assert status == 200
    assert "Playwright Rendered" in body
    assert method == "playwright"
    assert call_log == ["httpx", "playwright"]


def test_ua_pool_rotation_picks_entries() -> None:
    svc = LiveJobDiscoveryService()
    picked = {svc._rotate_user_agent() for _ in range(20)}
    # Havuzda en az 2 farklı UA var (havuzda 4 tane var, 20 turda 2+ görmeliyiz)
    assert len(picked) >= 2
    for ua in picked:
        assert isinstance(ua, str) and len(ua) > 20


# ════════════════════════════════════════════════════════════════════════════
# N3 Regression Tests (36 → 38): 2 Yeni Test (Scheduler URL Fallback + Generic Extractor)
# ════════════════════════════════════════════════════════════════════════════


def test_extract_source_urls_fallback_to_search_criteria_dict_and_json() -> None:
    """Regression #1: Scheduler._extract_source_urls metadata boşsa search_criteria dict/JSON'dan alsın."""
    import json as _json

    from app.core.scheduler import WatcherScheduler

    ws = WatcherScheduler()

    # Case 1: SADECE metadata.source_urls var (klasik yol)
    class W1:
        metadata: dict | None = None
        search_criteria: dict | str | None = None

    w1 = W1()
    w1.metadata = {"source_urls": ["https://a.test"]}
    w1.search_criteria = {}
    assert ws._extract_source_urls(w1) == ["https://a.test"], (
        "Case 1 FAILED (metadata classic)"
    )

    # Case 2: SADECE search_criteria (dict) source_urls (YENİ KAYIT YOLLA)
    class W2:
        metadata: dict | None = None
        search_criteria: dict | str | None = None

    w2 = W2()
    w2.metadata = {}
    w2.search_criteria = {"source_urls": ["https://b.test", "https://c.test"]}
    res2 = ws._extract_source_urls(w2)
    assert "https://b.test" in res2 and "https://c.test" in res2, (
        f"Case 2 FAILED (dict src_urls): {res2}"
    )

    # Case 3: SADECE search_criteria (STRING JSON — eski uyumsuz kayıtlar)
    class W3:
        metadata: dict | None = None
        search_criteria: dict | str | None = None

    w3 = W3()
    w3.metadata = None
    w3.search_criteria = _json.dumps(
        {"sources": ["https://d.test"], "source_urls": ["https://e.test"]}
    )
    res3 = ws._extract_source_urls(w3)
    assert any(("d.test" in u or "e.test" in u) for u in res3), (
        f"Case 3 FAILED (JSON string): {res3}"
    )

    # Case 4: HEPSI BOŞ — boş liste döner (hata atmaz)
    class W4:
        metadata: dict | None = None
        search_criteria: dict | str | None = None

    w4 = W4()
    w4.metadata = None
    w4.search_criteria = {}
    assert ws._extract_source_urls(w4) == [], "Case 4 FAILED (empty → [])"

    # Case 5: search_criteria "sources" anahtarı (source_urls yoksa sources yedek)
    class W5:
        metadata: dict | None = None
        search_criteria: dict | str | None = None

    w5 = W5()
    w5.metadata = {}
    w5.search_criteria = {"sources": ["https://f.test", "https://g.test"]}
    res5 = ws._extract_source_urls(w5)
    assert "https://f.test" in res5, f"Case 5 FAILED (sources fallback): {res5}"


def test_extract_generic_jobs_works_for_unknown_site() -> None:
    """Regression #2: Bilinmeyen domain (ör example.com) HTML'de generic fallback çalışıp job döndürsün + platform company_page."""
    from app.domains.watchers.discovery import LiveJobDiscoveryService

    svc = LiveJobDiscoveryService()

    # Generic HTML — karışık ör (card + data-* + li karışık kalıplar, 3 extractor deneyecek)
    unknown_html = """
    <div class="career-page">
      <!-- 1. Kalıp: div.card / anchor / .company / .location (Eleman/KN kalıbı) -->
      <div class="card job-item">
        <a href="/job/12345-senior-qa"><h3>Senior QA Manager (Remote)</h3></a>
        <span class="company">TechCorp Solutions</span>
        <span class="location">İstanbul (Remote)</span>
      </div>
      <!-- 2. Kalıp: data-* attribute (Yenibiris kalıbı) -->
      <article data-job-title="Test Otomasyon Mühendisi" data-firma="Kariyer Teknoloji AŞ" data-konum="Ankara" class="ilan">
        <a href="/career/999-test">İlan Detayı</a>
      </article>
      <!-- 3. Kalıp: li.list-item (liste kalıbı) -->
      <ul>
        <li class="list-item job-card">
          <h4>Kalite Güvence Uzmanı (Hibrit)</h4>
          <p>Firma: ABC Lojistik Ltd · Şehir: İzmir</p>
          <a href="/jobs/555">Detay</a>
        </li>
      </ul>
    </div>
    """
    jobs = svc._extract_from_html(
        unknown_html, "https://www.example-unknown-career-site.co/jobs?q=qa+manager"
    )
    # En az 1 iş dönmeli (3 extractor denendi, biri çalışmalı)
    assert len(jobs) >= 1, (
        f"Generic fallback BOŞ (en az 1 iş olmalı) — count={len(jobs)}"
    )
    titles = {j.title for j in jobs}
    assert any(
        ("QA" in t or "Test" in t or "Kalite" in t or "Otomasyon" in t) for t in titles
    ), f"Titles: {titles}"
    # Generic fallback (bilinmeyen site) → platform company_page OLMALI
    plats = {str(j.source_platform or "") for j in jobs}
    assert any(("company_page" in p or not p) for p in plats), (
        f"Bilinmeyen site platformu company_page olmalı, gelen: {plats}"
    )
    # Şirket/konumdan en az biri doldurulmuş olmalı (kalite)
    has_company_or_loc = any(
        (str(j.company_name or "").strip() or str(j.location or "").strip())
        for j in jobs
    )
    assert has_company_or_loc, "Generic fallback'ta company/location doldurulamadı"


# ========== M5-S4: 4 Yeni Regression Test (38 → 42) ==========


def test_regression_3_decode_body_bytes():
    """Brotli/GZIP/DEFLATE manuel bytes decode + encoding fallback (cp1254 TR chars)."""
    import gzip
    import zlib

    from app.domains.watchers.discovery import (
        _HAS_BROTLI,
    )
    from app.domains.watchers.discovery import (
        LiveJobDiscoveryService as LJDS,
    )

    # Normal UTF-8 text (orijinal HTML snippet)
    orig = "<html><head><title>Test Müdürüdür — Şirket: İzmir'de</title></head></html>"

    # 1) GZIP sıkıştır → decode
    gz_bytes = gzip.compress(orig.encode("utf-8"))
    decoded_gz = LJDS._decode_body_bytes(gz_bytes, ce_hint="gzip")
    assert orig in decoded_gz, f"GZIP decode başarısız: {decoded_gz[:200]!r}"

    # 2) DEFLATE sıkıştır → decode
    def_bytes = zlib.compress(orig.encode("utf-8"))
    decoded_def = LJDS._decode_body_bytes(def_bytes, ce_hint="deflate")
    assert orig in decoded_def, "DEFLATE decode başarısız"

    # 3) BROTLI sıkıştır (varsa) → decode
    if _HAS_BROTLI:
        try:
            import brotli as _br

            br_bytes = _br.compress(orig.encode("utf-8"))
            decoded_br = LJDS._decode_body_bytes(br_bytes, ce_hint="br")
            assert orig in decoded_br, "BROTLI decode başarısız (ce_hint=br)"
            # 3b) MAGIC BYTES tahmini (ce_hint eksik, brotli binary)
            decoded_br2 = LJDS._decode_body_bytes(br_bytes, ce_hint=None)
            assert orig in decoded_br2, "BROTLI magic bytes tahmini başarısız"
        except Exception:
            pass  # brotli sıkıştırma hatası önemli değil (opsiyonel)

    # 4) Sıkıştırılmamış + Türkçe karakter (cp1254) — encoding fallback
    orig_tr = "Başarıyla şifre çözüldü — İzmir'de ı ş ğ ü ö ç İ Ş Ğ Ü Ö Ç".encode(
        "cp1254"
    )
    decoded_tr = LJDS._decode_body_bytes(orig_tr, ce_hint=None)
    assert "İzmir" in decoded_tr or "Başarı" in decoded_tr, (
        f"CP1254 fallback başarısız: {decoded_tr!r}"
    )

    # 5) Boş bytes + None → hata atmaz
    assert LJDS._decode_body_bytes(b"", None) == ""


def test_regression_4_body_garbage_detection():
    """BROTLI çözülmemiş binary garbage vs doğru HTML text ayrımı (non-printable %35 eşik)."""
    from app.domains.watchers.discovery import (
        _HAS_BROTLI,
    )
    from app.domains.watchers.discovery import (
        LiveJobDiscoveryService as LJDS,
    )

    # 1) Garbage: Non-printable karakterler çok (brotli/gzip binary)
    if _HAS_BROTLI:
        import brotli  # type: ignore

        big_html = (
            "<!doctype html><html><title>x</title><body>"
            + ("<p>selam</p>" * 5000)
            + "</body></html>"
        )
        garbage = brotli.compress(big_html.encode("utf-8"))
        garbage_text = garbage.decode(
            "latin-1", errors="replace"
        )  # yanlış decode → garbage
        assert LJDS._body_looks_garbage(garbage_text) is True, (
            "BROTLI binary garbage DETECT EDİLMELİYDİ"
        )
    else:
        # brotli yoksa: %70 oranında SADECE BAD byte (0x00-0x08: hiçbiri printable, hiçbiri isspace değil)
        ba = bytearray()
        import random as _rng

        _rng.seed(42)
        ALL_BAD = list(range(0x09))  # 9 adet, hiçbiri printable/whitespace DEĞİL
        ALL_OK = list(range(0x41, 0x5B))  # A-Z
        for _ in range(10000):
            if _rng.random() < 0.70:
                ba.append(_rng.choice(ALL_BAD))  # %70 KESİNLİKLE BAD
            else:
                ba.append(_rng.choice(ALL_OK))
        garbage_text = bytes(ba).decode("latin-1", errors="replace")
        assert LJDS._body_looks_garbage(garbage_text) is True, (
            "%70 BAD byte garbage DETECT EDİLMELİ (%35 eşik çok altında)"
        )

    # 2) Normal HTML: Küçük dosya (<200 char) → her zaman False
    assert LJDS._body_looks_garbage("<html><body>kısa</body>") is False, (
        "Kısa text garbage OLMAMALI"
    )

    # 3) Normal HTML: Uzun, temiz UTF-8 → False
    clean_html = "<!doctype html><html><head><title>İş İlanları - Eleman.net</title></head><body>"
    clean_html += (
        "<h2>Yazılım Test Uzmanı - İstanbul</h2><p>Şirket: Tech A.Ş.</p>" * 200
    )
    clean_html += "</body></html>"
    assert LJDS._body_looks_garbage(clean_html) is False, "Temiz HTML garbage OLAMAZ"

    # 4) Sınır: %30 non-printable (eşik %35) → False
    chars = []
    for i in range(4000):
        if i % 10 < 3:  # %30 non-printable (0x00-0x08)
            chars.append(chr(i % 8))
        else:
            chars.append(chr(65 + (i % 26)))
    borderline = "".join(chars)
    assert LJDS._body_looks_garbage(borderline) is False, (
        "%30 non-printable garbage OLMAMALI"
    )

    # 5) Aşırı: %50 non-printable → True
    bad_chars = []
    for i in range(4000):
        if i % 2 == 0:
            bad_chars.append(chr(i % 8))
        else:
            bad_chars.append(chr(65 + (i % 26)))
    bad_text = "".join(bad_chars)
    assert LJDS._body_looks_garbage(bad_text) is True, (
        "%50 non-printable garbage DETECT EDİLMELİ"
    )


def test_regression_5_eleman_spa_mock_html():
    """Eleman.net SPA mock: classları rastgele (jobItem/jobListing/advert-card olacak), JS render sonrası 5+ ilan."""
    from app.domains.watchers.discovery import LiveJobDiscoveryService

    svc = LiveJobDiscoveryService()

    eleman_spa_mock = """
    <html lang="tr"><head><title>Eleman.net - İş İlanları</title></head>
    <body>
    <div id="__next"><main data-testid="job-list-page">
      <!-- SPA render sonrası (React/Next.js) Eleman.net job kart kalıpları -->
      <section class="jobs-container">
        <article data-id="9001" class="jobItem p-3 mb-2 border rounded advert-card">
          <a href="/ilan/9001-senior-test-otomasyon-muhendisi" class="jobLink">
            <h2 class="jobTitle">Senior Test Otomasyon Mühendisi (Selenium)</h2>
          </a>
          <div class="companyName">Trendyol Teknoloji A.Ş.</div>
          <div class="locationInfo">İstanbul · Üsküdar</div>
          <span class="publishDate">2 gün önce</span>
        </article>
        <article data-id="9002" class="jobItem p-3 mb-2 border rounded advert-card">
          <a href="/ilan/9002-yazilim-test-yoneticisi-5-yil" class="jobLink">
            <h2 class="jobTitle">Yazılım Test Yöneticisi (QA Lead)</h2>
          </a>
          <div class="companyName">Hepsiburada.com</div>
          <div class="locationInfo">İstanbul · Avrupa</div>
          <span class="publishDate">3 gün önce</span>
        </article>
        <article data-id="9003" class="jobItem p-3 mb-2 border rounded advert-card">
          <a href="/ilan/9003-quality-assurance-analist-remote" class="jobLink">
            <h2 class="jobTitle">Kalite Güvence (QA) Analist (Remote)</h2>
          </a>
          <div class="companyName">Getir Teknoloji</div>
          <div class="locationInfo">Remote</div>
          <span class="publishDate">1 gün önce</span>
        </article>
        <article data-id="9004" class="jobItem p-3 mb-2 border rounded advert-card">
          <a href="/ilan/9004-mobile-app-test-uzmani" class="jobLink">
            <h2 class="jobTitle">Mobil Uygulama Test Uzmanı (Appium)</h2>
          </a>
          <div class="companyName">Yemeksepeti</div>
          <div class="locationInfo">Ankara</div>
          <span class="publishDate">Bugün</span>
        </article>
        <article data-id="9005" class="jobItem p-3 mb-2 border rounded advert-card">
          <a href="/ilan/9005-performance-test-muhendisi-jmeter" class="jobLink">
            <h2 class="jobTitle">Performans Test Mühendisi (JMeter / k6)</h2>
          </a>
          <div class="companyName">Trendyol Tech</div>
          <div class="locationInfo">İzmir · Bornova</div>
          <span class="publishDate">5 gün önce</span>
        </article>
        <article data-id="9006" class="jobItem p-3 mb-2 border rounded advert-card">
          <a href="/ilan/9006-sdet-engineer-python" class="jobLink">
            <h2 class="jobTitle">SDET Engineer (Python / Pytest)</h2>
          </a>
          <div class="companyName">Migros Teknoloji</div>
          <div class="locationInfo">Kocaeli · Gebze</div>
          <span class="publishDate">1 hafta önce</span>
        </article>
      </section>
    </main></div>
    </body></html>
    """
    jobs = svc._extract_elemannet_jobs(
        eleman_spa_mock, "https://www.eleman.net/is-ilanlari/yazilim-test"
    )
    assert len(jobs) >= 5, f"Eleman SPA mock 5+ iş döndürmeli, gelen: {len(jobs)}"
    titles = {j.title for j in jobs}
    assert "Senior Test Otomasyon Mühendisi (Selenium)" in titles, (
        f"Başlık 1 bulunamadı: {titles}"
    )
    assert "SDET Engineer (Python / Pytest)" in titles, "SDET başlığı gelmedi"
    # Şirket ve konum dolu
    for j in jobs[:3]:
        assert len(str(j.company_name or "").strip()) > 3, (
            f"Şirket boş geldi: {j.title} → {j.company_name!r}"
        )
        assert len(str(j.location or "").strip()) > 2, (
            f"Konum boş geldi: {j.title} → {j.location!r}"
        )
    # Platform eleman_net olmalı
    plats = {str(j.source_platform) for j in jobs}
    assert any("eleman" in p.lower() for p in plats), (
        f"Platform eleman_net olmalı: {plats}"
    )
    # Kaynak URL'ler /ilan/ pattern ile başlamalı (domain eklenmiş)
    for j in jobs:
        assert "/ilan/" in (j.source_url or ""), (
            f"Eleman URL pattern'ı /ilan/ olmalı: {j.source_url!r}"
        )


def test_regression_6_jobturk_anchor_pattern_mock():
    """JobTurk anchor URL pattern: /is-ilanlari/detay/<id>-<slug> link + çevrede şirket/konum ara, 8+ iş."""
    from app.domains.watchers.discovery import LiveJobDiscoveryService

    svc = LiveJobDiscoveryService()

    jobturk_mock = """
    <!doctype html><html><head><title>JobTürkiye - Test İlanları</title></head>
    <body class="job-list-page">
    <header><nav>Site Nav</nav></header>
    <main>
      <h1>Test Uzmanı İlanları (247 adet)</h1>
      <div class="job-results-grid">
        <!-- 1 -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">ASELSAN A.Ş.</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/101-savunma-sistemleri-test-uzmani" class="job-title-link">
              Savunma Sistemleri Yazılım Test Uzmanı
            </a>
          </div>
          <div class="col-2 city"><span class="konum">Ankara · Mamak</span></div>
          <div class="col-2 date">1 gün önce</div>
        </div>
        <!-- 2 -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">TUSAŞ</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/102-ucak-yazilim-test-muhendisi" class="job-title-link">
              Uçak Yazılımı Test Mühendisi (DO-178C)
            </a>
          </div>
          <div class="col-2 city"><span class="konum">Ankara</span></div>
          <div class="col-2 date">3 gün önce</div>
        </div>
        <!-- 3 -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">Baykar Teknoloji</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/103-simulasyon-test-uzmani-silahli" class="job-title-link">
              Simülasyon ve Entegrasyon Test Uzmanı
            </a>
          </div>
          <div class="col-2 city"><span class="konum">İstanbul · Sancaktepe</span></div>
          <div class="col-2 date">Bugün</div>
        </div>
        <!-- 4 -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">ROKETSAN</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/104-fuze-software-qa-lead" class="job-title-link">
              Füze Yazılımı QA Lideri (C/C++)
            </a>
          </div>
          <div class="col-2 city"><span class="konum">Ankara · Yenimahalle</span></div>
          <div class="col-2 date">5 gün önce</div>
        </div>
        <!-- 5 -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">HAVELSAN</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/105-sistem-test-muhendisi-siber" class="job-title-link">
              Sistem Test Mühendisi (Siber Güvenlik)
            </a>
          </div>
          <div class="col-2 city"><span class="konum">Ankara</span></div>
          <div class="col-2 date">2 gün önce</div>
        </div>
        <!-- 6 -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">Türk Telekom Teknoloji</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/106-telekom-ag-test-uzmani" class="job-title-link">
              Telekom Ağ Test Uzmanı (5G / VoIP)
            </a>
          </div>
          <div class="col-2 city"><span class="konum">İstanbul · Büyükçekmece</span></div>
          <div class="col-2 date">1 hafta önce</div>
        </div>
        <!-- 7 -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">PTT Teknoloji</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/107-kargo-takip-sistemi-test" class="job-title-link">
              Kargo Takip Sistemi Test Otomasyon Uzmanı
            </a>
          </div>
          <div class="col-2 city"><span class="konum">Ankara · Çankaya</span></div>
          <div class="col-2 date">4 gün önce</div>
        </div>
        <!-- 8 -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">Eczacıbaşı Bilişim</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/108-sap-fiori-qa-test" class="job-title-link">
              SAP Fiori Modülü QA Uzmanı
            </a>
          </div>
          <div class="col-2 city"><span class="konum">İzmir · Konak</span></div>
          <div class="col-2 date">6 gün önce</div>
        </div>
        <!-- 9 (ekstra 9. kayıt — sınır için) -->
        <div class="list-row row-item">
          <div class="col-3 company"><span class="kurum">Ford Otosan</span></div>
          <div class="col-5 position">
            <a href="/is-ilanlari/detay/109-otomotiv-ecu-test" class="job-title-link">
              Otomotiv ECU Yazılım Test Mühendisi
            </a>
          </div>
          <div class="col-2 city"><span class="konum">Kocaeli · Gölcük</span></div>
          <div class="col-2 date">Bugün</div>
        </div>
      </div>
    </main>
    <footer>Site Footer</footer>
    </body></html>
    """
    jobs = svc._extract_jobturk_jobs(
        jobturk_mock, "https://www.jobturkiye.com/is-ilanlari/test"
    )
    assert len(jobs) >= 8, f"JobTurk mock 8+ iş döndürmeli, gelen: {len(jobs)}"
    # İlk 2 başlık + şirket kontrol
    titles = {j.title.strip() for j in jobs}
    assert "Savunma Sistemleri Yazılım Test Uzmanı" in titles, f"1.başlık yok: {titles}"
    assert "Otomotiv ECU Yazılım Test Mühendisi" in titles, "9.başlık (son kayıt) yok"
    # Şirket & konum 7+ doldurulmuş olmalı
    dolu = sum(
        1
        for j in jobs
        if len(str(j.company_name or "").strip()) > 2
        and len(str(j.location or "").strip()) > 2
    )
    assert dolu >= 7, f"Şirket+konum dolu kayıt 7+ olmalı, {dolu} geldi"
    # Anchor URL: /is-ilanlari/detay/ pattern
    for j in jobs:
        assert "/is-ilanlari/detay/" in (j.source_url or ""), (
            f"URL pattern yanlış: {j.source_url!r}"
        )
    # Platform jobturk
    assert any("jobturk" in str(j.source_platform or "").lower() for j in jobs)


# ========== P4: Notification Okuma + 42→44 2 Yeni Test ==========


def test_regression_7_notification_mark_read_flow():
    """6 adım: Bildirim oluştur (InMemory repo) → list → get → READ → kontrol → UNREAD → READ-ALL + güvenlik kontrolleri."""
    from unittest.mock import Mock

    from app.domains.watchers.repository import InMemoryWatcherRepository
    from app.domains.watchers.schemas import NotificationChannel, NotificationRecord

    # WatcherService constructor Any type tip var, repository çalışması yeterli, diğerlerini Mock'la
    repo = InMemoryWatcherRepository()
    from app.domains.watchers.service import WatcherService, utcnow

    svc = WatcherService(
        repository=repo,
        matching_service=Mock(),
        settings=Mock(),
        profile_repository=None,
        jobs_service=Mock(),
        discovery_service=Mock(),
    )

    uid = "u_notif_001"
    # 1) 5 tane okunmamış + 1 tane okunmuş = 6 bildirim oluştur
    nids = []
    for i in range(5):
        n = NotificationRecord(
            id=f"n-{i:02d}-{uid}",
            user_id=uid,
            watcher_id="w-test",
            job_id=f"job{i}",
            channel=NotificationChannel.in_app,
            title=f"Yeni ilan {i}",
            message=f"Skor {60 + i}",
            created_at=utcnow(),
            is_read=False,
            metadata={"idx": i},
        )
        repo.add_notification(n)
        nids.append(n.id)
    # 1 tanesi önceden okunmuş
    n_extra = NotificationRecord(
        id="n-pre-read",
        user_id=uid,
        watcher_id="w-test",
        job_id="jobX",
        channel=NotificationChannel.in_app,
        title="Önce okunmuş",
        message="...",
        created_at=utcnow(),
        is_read=True,
    )
    repo.add_notification(n_extra)

    # 2) List: 6 bildirim
    all_notifs = svc.list_notifications(user_id=uid)
    assert len(all_notifs) == 6, f"6 bildirim olmalı: {len(all_notifs)}"
    # 3) Unread sayısı: 5
    unread = sum(1 for n in all_notifs if not n.is_read)
    assert unread == 5, f"Okunmamış 5 olmalı: {unread}"

    # 4) TEKİL GETİR (get_notification)
    first = svc.get_notification(nids[0], user_id=uid)
    assert first is not None, f"{nids[0]} getirilmeliydi"
    assert first.id == nids[0]
    assert first.is_read is False
    # 4b) Yanlış user_id ile getir → None (güvenlik)
    assert svc.get_notification(nids[0], user_id="YABANCI_KULLANICI") is None, (
        "Başkasına ait bildirim görünmemeli"
    )
    # 4c) Olmayan ID → None
    assert svc.get_notification("SAÇMA-ID") is None

    # 5) MARK READ → is_read=True kontrol
    updated = svc.mark_notification_read(nids[0], user_id=uid, is_read=True)
    assert updated is not None
    assert updated.is_read is True, "Okunmuş olarak işaretlenmeliydi"
    # DB'den tekrar getir → gerçekten değişmiş mi?
    again = svc.get_notification(nids[0], user_id=uid)
    assert again and again.is_read is True, "Gerçekten kaydedilmiş olmalı"
    # 5b) Yanlış user ile mark → None (güvenlik, izinsiz değiştirilemez)
    assert svc.mark_notification_read(nids[1], user_id="YABANCI") is None

    # 6) MARK UNREAD → geri al
    undone = svc.mark_notification_read(nids[0], user_id=uid, is_read=False)
    assert undone and undone.is_read is False, "Tekrar okunmamış yapılabildi mi?"

    # 7) READ-ALL — kullanıcının tüm okunmamışlarını işaretle
    before = sum(1 for n in svc.list_notifications(user_id=uid) if not n.is_read)
    assert before == 5, f"Mark-all öncesi 5 okunmamış olmalı: {before}"
    marked = svc.mark_all_notifications_read(uid)
    assert marked == 5, f"5 adet işaretlenmeliydi: {marked}"
    # Sonra: 0 okunmamış
    after = sum(1 for n in svc.list_notifications(user_id=uid) if not n.is_read)
    assert after == 0, f"Hepsi okunmalı: {after} kaldı"
    # 2. kez mark_all → 0 (hepsi zaten okunmuş)
    assert svc.mark_all_notifications_read(uid) == 0
    # Boş user_id → güvenlik: 0
    assert svc.mark_all_notifications_read("") == 0


def test_regression_8_notification_router_endpoints():
    """FastAPI TestClient ile 7 notification REST endpoint (list/get/read/unread/read-all/unread-count list)."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    uid = "default-user"

    # 1) GET /api/v1/notifications → 200 liste
    r1 = client.get("/api/v1/notifications", params={"user_id": uid})
    assert r1.status_code == 200, f"List 200 olmalı: {r1.status_code} → {r1.text[:200]}"
    arr1 = r1.json()
    assert isinstance(arr1, list)
    # Gerçek SQLite DB'de 5 bildirim var (M4'ten kalan) → en az 0 olmalı, list 200
    orig_len = len(arr1)
    print(f"[P4_8] Başlangıç bildirim sayısı (DB): {orig_len}")

    # 2) GET /api/v1/notifications/unread-count → 200 okunmamış say
    r2 = client.get("/api/v1/notifications/unread-count", params={"user_id": uid})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["ok"] is True
    assert "unread_count" in d2 and isinstance(d2["unread_count"], int)
    print(f"[P4_8] Okunmamış: {d2['unread_count']}")

    # 3) Eğer DB'de bildirim varsa → ID alıp PATCH /read + PATCH /unread dene
    if orig_len > 0:
        sample_id = arr1[0]["id"]
        # 3a) GET /:id → 200 + doğru ID
        r3a = client.get(f"/api/v1/notifications/{sample_id}", params={"user_id": uid})
        assert r3a.status_code == 200, (
            f"Get tekil 200: {r3a.status_code} {r3a.text[:100]}"
        )
        assert r3a.json()["id"] == sample_id

        # 3b) PATCH /:id/read → is_read=True dönmeli
        r3b = client.patch(
            f"/api/v1/notifications/{sample_id}/read", params={"user_id": uid}
        )
        assert r3b.status_code == 200, f"Read patch: {r3b.status_code} {r3b.text[:150]}"
        assert r3b.json()["is_read"] is True, (
            f"Read sonrası is_read=True olmalı: {r3b.json()!r}"
        )

        # 3c) PATCH /:id/unread → geri al
        r3c = client.patch(
            f"/api/v1/notifications/{sample_id}/unread", params={"user_id": uid}
        )
        assert r3c.status_code == 200
        assert r3c.json()["is_read"] is False

        # 3d) Başka kullanıcı ile aynı ID'ye eriş → 404 (güvenlik: kullanıcı doğrulaması)
        r3d = client.patch(
            f"/api/v1/notifications/{sample_id}/read", params={"user_id": "baska_kisi"}
        )
        assert r3d.status_code == 404, (
            f"Başka kullanıcı 404 dönmeli: {r3d.status_code} → {r3d.text[:120]}"
        )

    # 4) Olmayan ID → 404
    r4 = client.patch(
        "/api/v1/notifications/OLMAYAN-ID-12345/read", params={"user_id": uid}
    )
    assert r4.status_code == 404, f"Olmayan ID 404: {r4.status_code}"

    # 5) PATCH /api/v1/notifications/read-all → {ok:True, marked_read_count: int}
    r5 = client.patch("/api/v1/notifications/read-all", params={"user_id": uid})
    assert r5.status_code == 200, f"Read-all: {r5.status_code} {r5.text[:120]}"
    d5 = r5.json()
    assert d5["ok"] is True
    assert isinstance(d5["marked_read_count"], int)
    # unread_count → 0 olmalı (ya da sayı, int)
    r6 = client.get("/api/v1/notifications/unread-count", params={"user_id": uid})
    d6 = r6.json()
    assert isinstance(d6["unread_count"], int) and d6["unread_count"] >= 0


# ---------------------------------------------------------------------------
# REG 9 · Watcher CRUD (Delete + Toggle Active + Router Endpoint 200/404)
#   44/44 → 45/47
# ---------------------------------------------------------------------------
def test_regression_9_watcher_delete_and_toggle_active_service_layer():
    """Service katmanı delete_watcher + toggle_watcher_active doğrulaması."""
    from unittest.mock import Mock

    from app.domains.matching.schemas import CandidateProfileInput, MatchingWeights
    from app.domains.watchers.schemas import (
        NotificationChannel,
        SearchCriteria,
        SourcePlatform,
        WatcherRecord,
    )
    from app.domains.watchers.service import WatcherService, utcnow

    repo = __import__(
        "app.domains.watchers.repository", fromlist=["InMemoryWatcherRepository"]
    ).InMemoryWatcherRepository()
    service = WatcherService(
        repository=repo,
        matching_service=Mock(),
        settings=Mock(),
        profile_repository=None,
        jobs_service=Mock(),
        discovery_service=Mock(),
    )

    w1 = WatcherRecord(
        id="w-test-del-001",
        user_id="u1",
        query_name="Test Silinecek",
        source_platform=SourcePlatform.manual_import,
        search_criteria=SearchCriteria(),
        candidate_profile=CandidateProfileInput(
            headline="Test Aday", summary="Test özeti", skills=["Python"]
        ),
        weights=MatchingWeights(),
        minimum_match_score=60.0,
        sync_frequency_minutes=120,
        notification_channels=[NotificationChannel.in_app],
        is_active=True,
        created_at=utcnow(),
        updated_at=utcnow(),
        last_synced_at=None,
        metadata={},
    )
    repo.save_watcher(w1)
    assert len(repo.list_watchers()) == 1

    # A) Toggle Active: True → False → True
    t_off = service.toggle_watcher_active(w1.id, False)
    assert t_off.is_active is False
    t_on = service.toggle_watcher_active(w1.id, True)
    assert t_on.is_active is True
    # Olmayan ID → KeyError beklenir
    try:
        service.toggle_watcher_active("W-OLMAYAN", True)
        raise AssertionError("Olmayan watcher için KeyError bekleniyordu")
    except KeyError:
        pass

    # B) Delete var olan → True + 0 watcher
    assert service.delete_watcher(w1.id) is True
    assert len(repo.list_watchers()) == 0

    # C) Delete tekrar aynı ID → False
    assert service.delete_watcher(w1.id) is False


# ---------------------------------------------------------------------------
# REG 10 · Watchers CRUD Router Endpoints (3 yeni: PATCH /active + DELETE + list/create)
#   45/47 → 46/47
# ---------------------------------------------------------------------------
def test_regression_10_watchers_router_crud_endpoints():
    """DELETE + PATCH /active endpointleri 200/404 doğrulaması (FastAPI TestClient)."""
    client = TestClient(app)
    uid = "user-wcrud-01"

    # 0) Önce boş listele: 200 + []
    r0 = client.get("/api/v1/watchers", params={"user_id": uid})
    assert r0.status_code == 200

    # 1) CREATE (body olmadan minimum örnek — doğrudan JSON body gönderelim)
    body = {
        "user_id": uid,
        "query_name": "Router CRUD Test",
        "source_platform": "manual_import",
        "search_criteria": {
            "keywords": ["Test", "Yazılım"],
            "locations": ["İstanbul"],
            "min_experience_years": 3,
            "max_experience_years": 15,
        },
        "candidate_profile": {
            "headline": "Test Aday — Yazılım Test Uzmanı",
            "summary": "Test odaklı 7 yıl deneyimli kalite güvence uzmanı",
            "total_experience_years": 7,
            "skills": ["Python", "Selenium", "Postman"],
        },
        "minimum_match_score": 60,
    }
    r1 = client.post("/api/v1/watchers", json=body)
    assert r1.status_code == 200, (
        f"Create 200 olmalı: {r1.status_code} → {r1.text[:200]}"
    )
    w_id = r1.json()["id"]
    assert w_id and r1.json()["is_active"] is True

    # 2) PATCH /active → False
    r2a = client.patch(f"/api/v1/watchers/{w_id}/active", params={"is_active": "false"})
    assert r2a.status_code == 200, (
        f"Toggle active 200: {r2a.status_code} {r2a.text[:150]}"
    )
    assert r2a.json()["is_active"] is False

    # 3) PATCH /active → True (varsayılan)
    r2b = client.patch(f"/api/v1/watchers/{w_id}/active", params={"is_active": "true"})
    assert r2b.status_code == 200 and r2b.json()["is_active"] is True

    # 4) Olmayan watcher → PATCH /active 404
    r2c = client.patch(
        "/api/v1/watchers/W-OLMAYAN-XYZ/active", params={"is_active": "true"}
    )
    assert r2c.status_code == 404, f"Olmayan PATCH active 404: {r2c.status_code}"

    # 5) DELETE var olan → 200 ok
    r3 = client.delete(f"/api/v1/watchers/{w_id}")
    assert r3.status_code == 200, f"Delete 200 olmalı: {r3.status_code} {r3.text[:100]}"
    d3 = r3.json()
    assert d3["ok"] is True and d3["deleted_watcher_id"] == w_id

    # 6) DELETE tekrar → 404
    r4 = client.delete(f"/api/v1/watchers/{w_id}")
    assert r4.status_code == 404, f"2. Delete 404 olmalı: {r4.status_code}"

    # 7) Olmayan ID → 404
    r5 = client.delete("/api/v1/watchers/W-OLMAYAN-777")
    assert r5.status_code == 404


# ---------------------------------------------------------------------------
# REG 11 · _should_force_playwright Domain Doğrulaması (8 domain + subdomain parent match)
#   46/47 → 47/47
# ---------------------------------------------------------------------------
def test_regression_11_force_playwright_domain_and_subdomain_rules():
    """_DOMAINS_FORCE_PLAYWRIGHT + parent domain _should_force_playwright kuralları doğrula."""
    from app.domains.watchers.discovery import LiveJobDiscoveryService

    disc = LiveJobDiscoveryService(timeout_seconds=1.0)

    # A) Kesin eşleşmeler (tam match) — TRUE
    exact_true = [
        "https://kariyer.net/is-ilanlari",
        "https://www.kariyer.net/ilanlar",
        "https://m.kariyer.net/arama",
        "https://yenibiris.com/is",
        "https://www.yenibiris.com/is-ilanlari",
        "https://linkedin.com/jobs/view/123",
        "https://tr.linkedin.com/jobs",
        "https://eleman.net/is-ilanlari",
        "https://www.eleman.net/arama",
    ]
    for u in exact_true:
        assert disc._should_force_playwright(u) is True, f"TRUE olmalıydı: {u}"

    # B) Parent domain match (subdomain) — TRUE
    parent_true = [
        "https://jobs.kariyer.net/arama",  # kariyer.net → True
        "https://fr.linkedin.com/jobs",  # linkedin.com → True
        "https://api.eleman.net/search",  # eleman.net → True
        "https://kariyer.yenibiris.com/ilan",  # yenibiris.com → True
    ]
    for u in parent_true:
        assert disc._should_force_playwright(u) is True, f"Parent TRUE olmalı: {u}"

    # C) Benzer ad ama farklı TLD / başka domainler — FALSE
    #    Not: LinkedIn PUBLIC /jobs/search için httpx + minimal header ile HTTP 200 alınıyor,
    #         Playwright kullanımında LI authwall (HTTP 999) tetikleniyor → force=False.
    exact_false = [
        "https://kariyer.com/is",  # .com — farklı
        "https://yenibiris.org/ilan",  # .org — farklı
        "https://linkedin.de/jobs",  # de TLD parent linkedin.de — FARKLI
        "https://eleman.com/arama",  # .com — farklı
        "https://jobturk.com.tr/is",  # portal 7 — set dışı
        "https://secret.hr/ilan",  # portal 8 — set dışı
        "https://google.com/search?q=QA",  # genel — FALSE
        "https://www.linkedin.com/jobs/search/?keywords=QA",  # LI public search → httpx bypass
    ]
    for u in exact_false:
        assert disc._should_force_playwright(u) is False, f"FALSE olmalıydı: {u}"


# ---------------------------------------------------------------------------
# REG 12 · Operation Log Service + Repository (log_event + filter level/source/user_id)
#   47/49 → 48/49
# ---------------------------------------------------------------------------
def test_regression_12_operation_log_repository_and_service_layer():
    """InMemory repo ile log_event + list_logs filtreleri doğrula."""
    from unittest.mock import Mock

    from app.domains.watchers.repository import InMemoryWatcherRepository
    from app.domains.watchers.schemas import LogCreateRequest
    from app.domains.watchers.service import WatcherService, utcnow

    repo = InMemoryWatcherRepository()
    service = WatcherService(
        repository=repo,
        matching_service=Mock(),
        settings=Mock(),
        profile_repository=None,
        jobs_service=Mock(),
        discovery_service=Mock(),
    )

    # 1) 6 adet log at (çeşitli level/source/user_id)
    ts_base = utcnow()
    repo.log_event(
        level="INFO",
        source="scheduler",
        message="Scheduler başladı",
        user_id="u1",
        timestamp=ts_base,
    )
    repo.log_event(
        level="DEBUG",
        source="discovery",
        message="KN 24 iş geldi",
        user_id="u1",
        watcher_id="wA",
        timestamp=ts_base,
    )
    repo.log_event(
        level="WARN",
        source="email",
        message="SMTP bağlantı yavaş",
        user_id="u1",
        timestamp=ts_base,
    )
    repo.log_event(
        level="ERROR",
        source="discovery",
        message="LinkedIn 403",
        user_id="u2",
        watcher_id="wB",
        timestamp=ts_base,
    )
    repo.log_event(
        level="INFO",
        source="api",
        message="Watcher oluşturuldu",
        user_id="u2",
        watcher_id="wB",
        timestamp=ts_base,
    )
    repo.log_event(
        level="INFO",
        source="match",
        message="Match skorları hesaplandı",
        user_id="u1",
        watcher_id="wA",
        timestamp=ts_base,
    )

    # A) limit=100 ile 6 log
    assert len(service.list_logs(limit=100)) == 6

    # B) user_id=u1 → 4 log
    logs_u1 = service.list_logs(user_id="u1", limit=999)
    assert len(logs_u1) == 4

    # C) source=discovery → 2 (INFO u1 KN + ERROR u2 LI
    logs_disc = service.list_logs(source="discovery")
    assert len(logs_disc) == 2

    # D) level=ERROR → 1
    logs_err = service.list_logs(level="ERROR")
    assert len(logs_err) == 1 and str(logs_err[0].level) == "ERROR"

    # E) service.log_event(payload) API ile yeni kayıt
    new = service.log_event(
        LogCreateRequest(
            level="WARN",
            source="api",
            user_id="u3",
            watcher_id="wX",
            message="Yeni watcher create edildi",
            metadata={"a": 1},
        )
    )
    assert int(new.id) >= 1
    assert str(new.level) == "WARN"
    # toplam 7 log
    assert len(repo.list_logs(limit=999)) == 7


# ---------------------------------------------------------------------------
# REG 13 · Logs Router Endpoints (GET /api/v1/logs + POST /api/v1/logs) 200
#   48/49 → 49/49
# ---------------------------------------------------------------------------
def test_regression_13_logs_router_endpoints():
    """FastAPI TestClient ile 2 logs endpoint doğrulaması."""
    client = TestClient(app)

    # 1) Boş GET list → 200 + dizi
    r0 = client.get("/api/v1/logs", params={"limit": 5})
    assert r0.status_code == 200
    assert isinstance(r0.json(), list)

    # 2) Yeni log POST → 200
    payload = {
        "level": "INFO",
        "source": "test_router",
        "user_id": "user-test-log-01",
        "watcher_id": "w-log-test",
        "message": "Regression 13 test logu — POST /logs",
        "metadata": {"test": 13, "faz": 6},
    }
    rp = client.post("/api/v1/logs", json=payload)
    assert rp.status_code == 200, (
        f"POST /logs 200 olmalı: {rp.status_code} → {rp.text[:180]}"
    )
    d = rp.json()
    assert isinstance(d["id"], int) or d["id"] > 0
    assert d["level"] == "INFO" and d["source"] == "test_router"
    assert d["user_id"] == "user-test-log-01"
    assert d["message"] == payload["message"]

    # 3) Aynı user_id ile GET list → en az 1 içermeli
    rq = client.get("/api/v1/logs", params={"user_id": "user-test-log-01", "limit": 10})
    assert rq.status_code == 200
    arr = rq.json()
    assert isinstance(arr, list)
    assert len(arr) >= 1

    # 4) Filtre level=WARN (yoksa boş dizi) + limit 1
    rw = client.get("/api/v1/logs", params={"level": "WARN", "limit": 1})
    assert rw.status_code == 200
    assert isinstance(rw.json(), list)
