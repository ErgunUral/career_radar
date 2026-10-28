#!/usr/bin/env python3
"""F10_3: Direkt servis katmanı üzerinden Watcher Create → Discover → Archive INSERT + Match Score."""
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))
os.chdir(Path(__file__).parent / "apps" / "api")

from app.core.config import get_settings  # noqa: E402
from app.core.database import init_database  # noqa: E402
from app.domains.jobs.repository import jobs_repository  # noqa: E402
from app.domains.matching.service import HybridMatchingService  # noqa: E402
from app.domains.jobs.service import JobsService  # noqa: E402
from app.domains.jobs.parser import JobParser  # noqa: E402
from app.domains.profile.repository import profile_repository  # noqa: E402
from app.domains.watchers.db_repository import db_repository  # noqa: E402
from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402
from app.domains.watchers.service import WatcherService  # noqa: E402
from app.domains.watchers.schemas import (  # noqa: E402
    WatcherCreateRequest,
    WatcherDiscoverRequest,
    WatcherRunRequest,
    NotificationChannel,
    SourcePlatform,
)
from app.domains.matching.schemas import WorkMode  # noqa: E402

LI_URLS = [
    "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0",
    "https://www.linkedin.com/jobs/search?keywords=QA%20Engineer&location=T%C3%BCrkiye&position=1&pageNum=0",
]


def build_payload(user_id: str):
    return WatcherCreateRequest(
        user_id=user_id,
        query_name="F10_3-SERVICE Test/QA Watcher (Direct)",
        source_platform="linkedin_search_url",
        search_criteria={
            "keywords": ["test", "manager", "qa", "automation"],
            "locations": ["İstanbul", "Ankara", "Remote"],
            "industries": ["technology", "fintech"],
            "work_modes": [WorkMode.hybrid, WorkMode.remote],
            "min_experience_years": 3,
            "max_experience_years": 12,
            "position_types": ["full-time"],
        },
        candidate_profile={
            "candidate_id": f"cand-{uuid.uuid4().hex[:8]}",
            "headline": "Senior QA & Test Manager | Test Automation SDET",
            "summary": "5+ yıl yazılım testi ve test otomasyonu. Selenium, Cypress, Playwright uzmanlığı. QA süreçleri, CI/CD entegrasyonu, performans testleri.",
            "total_experience_years": 6.0,
            "management_years": 2.0,
            "team_size_managed": 4,
            "skills": [
                "selenium", "cypress", "playwright", "test automation",
                "api testing", "python", "jira", "postman",
                "jenkins", "sql", "manual testing", "istqb",
            ],
            "industries": ["teknoloji", "fintech", "saas"],
            "languages": ["Türkçe", "İngilizce"],
            "certifications": ["ISTQB Advanced", "Selenium WebDriver"],
            "educations": ["Lisans: Bilgisayar Mühendisliği"],
            "preferred_locations": ["İstanbul", "Remote", "Ankara"],
            "work_modes": [WorkMode.hybrid, WorkMode.remote],
            "salary_expectation": 85000,
        },
        weights={
            "skills_weight": 0.35, "experience_weight": 0.25,
            "location_weight": 0.15, "salary_weight": 0.10,
            "industry_weight": 0.10, "education_weight": 0.05,
        },
        minimum_match_score=45.0,
        sync_frequency_minutes=120,
        notification_channels=[NotificationChannel.email],
    )


def main() -> int:
    print("=" * 70)
    print("F10_3 (Direct Service Layer): Create → Discover → Archive + Match")
    print("=" * 70)

    settings = get_settings()
    init_database()
    matching_svc = HybridMatchingService(settings=settings)
    jobs_svc = JobsService(
        repository=jobs_repository,
        profile_repository=profile_repository,
        matching_service=matching_svc,
        parser=JobParser(),
    )
    discovery = LiveJobDiscoveryService(timeout_seconds=45.0)
    svc = WatcherService(
        repository=db_repository,
        matching_service=matching_svc,
        settings=settings,
        profile_repository=profile_repository,
        jobs_service=jobs_svc,
        discovery_service=discovery,
    )

    user_id = f"user-f10-{uuid.uuid4().hex[:6]}"
    print(f"\n[1] Yeni user_id: {user_id}")

    # 1) Create Watcher
    try:
        w = svc.create_watcher(build_payload(user_id))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ❌ Create watcher FAILED: {e}")
        return 2
    print(f"  ✅ Watcher yaratıldı: id={w.id}  name={w.query_name}")

    # 2) Ölçüm - Önceki durum
    pre_runs = len(svc.list_runs(w.id))
    pre_arch = len(svc.list_archive(user_id=user_id))
    print(f"  [Önce] runs={pre_runs}   archives={pre_arch}")

    # 3) Discover!
    req = WatcherDiscoverRequest(
        triggered_by="f10_3_direct_service",
        max_jobs=50,
        source_urls=LI_URLS,
    )
    t0 = time.time()
    print("\n[3] Discover (50 job max, 2 LI URL)...", flush=True)
    try:
        resp = svc.discover_jobs(w.id, req)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ❌ Discover FAILED: {e}")
        discovery.close_playwright_pool()
        return 3
    dt = time.time() - t0
    discovery.close_playwright_pool()

    run = resp.run
    imported = resp.imported_jobs or []
    archived = resp.archived_jobs or []
    reports = resp.source_reports or []
    print(f"  ✅ Discover OK · {dt:.1f}s")
    print(f"     Run id: {run.id}   status={run.status}")
    print(f"     processed={run.processed_jobs}  matched={run.matched_jobs}  archived(len)={len(archived)}  notifications_created={run.notifications_created}")
    print(f"     imported_jobs (returned): {len(imported)}")
    print(f"     source reports: {len(reports)}")
    for r in reports:
        note = (r.verification_note or "")[:90]
        err = (r.error_message or "")[:60]
        print(f"       · {(r.source_url or '')[:60]}")
        print(f"         status={r.status}  jobs={r.fetched_jobs}  platform={r.source_platform}")
        if note:
            print(f"         note: {note}")
        if err:
            print(f"         err : {err!r}")

    # Match score analiz — archive kayıtlarında last_match_score var
    scores = [float(a.last_match_score) for a in archived if isinstance(a.last_match_score, (int, float))]
    if scores:
        avg = sum(scores) / len(scores)
        pct50 = 100.0 * sum(1 for s in scores if s >= 50.0) / len(scores)
        print(f"\n  Match Score Analizi (örneklem={len(scores)} — archive last_match_score):")
        print(f"     avg   = %{avg:.1f}")
        print(f"     med   = %{sorted(scores)[len(scores)//2]:.1f}")
        print(f"     ≥%50  = %{pct50:.0f}  ({sum(1 for s in scores if s>=50)}/{len(scores)})")
        for i, a in enumerate(archived[:5]):
            title = (a.title or "")[:55]
            company = (a.company_name or "")[:25]
            ms = a.last_match_score
            print(f"     [{i+1}] %{ms:.0f}  {title!r}  @{company!r}")
    else:
        # Archive boşsa imported jobs (analysis_result) üzerinden puan al
        scores = []
        for j in imported[:50]:
            ar = j.analysis_result
            if ar and hasattr(ar, "total_score"):
                s = float(ar.total_score or 0)
                if s > 0:
                    scores.append(s)
        if scores:
            print(f"\n  [Fallback] Match Score (imported.analysis_result.total_score, n={len(scores)}):")
            print(f"     avg   = %{sum(scores)/len(scores):.1f}")

    # 4) Delta ölçüm (son)
    post_runs = len(svc.list_runs(w.id))
    post_arch = len(svc.list_archive(user_id=user_id))
    d_runs = post_runs - pre_runs
    d_arch = post_arch - pre_arch
    print(f"\n  [Delta] watcher_runs={d_runs:+d}  job_archives={d_arch:+d}")

    # 5) Sonuç
    ok = (
        d_runs >= 1
        and d_arch >= 1
        and len(archived) >= 1
    )
    scores_avg = (sum(scores) / len(scores)) if scores else 0.0
    ok = ok and scores_avg >= 50.0
    sc_ok = (
        f"  (avg match=%{scores_avg:.0f} ≥ %50: {'✓' if scores_avg>=50 else '✗'})"
        if scores
        else "  (⚠️ skor listesi boş!)"
    )
    print()
    print("=" * 70)
    print(f"SONUÇ: {'✅ F10_3 TAMAM' if ok else '⚠️ Eksik'}")
    print(f"       Δwatcher_runs = {d_runs:+d} {'✓' if d_runs>=1 else '✗'}  (hedef ≥ +1)")
    print(f"       Δjob_archives = {d_arch:+d} {'✓' if d_arch>=1 else '✗'}  (hedef ≥ +1)")
    if scores:
        pct50fin = 100.0 * sum(1 for s in scores if s >= 50.0) / len(scores)
        print(f"       avg_match_score = %{scores_avg:.0f} {'✓' if scores_avg>=50 else '✗'}  (hedef ≥ %50)")
        print(f"       jobs ≥%50 = {sum(1 for s in scores if s>=50)}/{len(scores)}  (%{pct50fin:.0f})")
    print(sc_ok)
    print("=" * 70)
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
