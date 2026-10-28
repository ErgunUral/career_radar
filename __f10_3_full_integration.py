#!/usr/bin/env python3
"""F10_3: Gerçek API üzerinden Watcher Create → Discover → Archive INSERT + Match Score."""
import json
import sys
import time
from pathlib import Path

import httpx

API = "http://localhost:8000"
UID = "user-ergun"

LI_URLS = [
    "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0",
    "https://www.linkedin.com/jobs/search?keywords=QA%20Engineer&location=T%C3%BCrkiye&position=1&pageNum=0",
]


def api_call(method: str, path: str, **kwargs):
    # Discover → match + archive INSERT uzun sürebilir → 15 dakika timeout
    if "discover" in path or "run" in path:
        kwargs.setdefault("timeout", 900)
    else:
        kwargs.setdefault("timeout", 60)
    r = httpx.request(method, API + path, **kwargs)
    try:
        data = r.json()
    except Exception:
        data = r.text
    return r.status_code, data


def main() -> int:
    print("=" * 70)
    print("F10_3: Watcher Create → Discover → Archive INSERT + Match Score")
    print("=" * 70)

    # 1) Profil + Watcher Yarat
    payload = {
        "user_id": UID,
        "query_name": "F10_3 Test Yöneticisi / QA Watcher",
        "source_platform": "linkedin_search_url",
        "search_criteria": {
            "keywords": ["test", "manager", "qa", "automation"],
            "locations": ["İstanbul", "Ankara", "İzmir", "Remote"],
            "industries": ["technology", "fintech"],
            "work_modes": ["hybrid", "remote", "onsite"],
            "min_experience_years": 3,
            "max_experience_years": 12,
            "position_types": ["full-time"],
        },
        "candidate_profile": {
            "candidate_id": "cand-f10-ergun",
            "headline": "Senior QA & Test Manager | Test Automation SDET",
            "summary": "5+ yıl yazılım testi ve test otomasyonu. Selenium, Cypress, Playwright uzmanlığı. QA süreçleri, CI/CD entegrasyonu, performans testleri.",
            "total_experience_years": 6.0,
            "management_years": 2.0,
            "team_size_managed": 4,
            "skills": [
                "selenium",
                "cypress",
                "playwright",
                "test automation",
                "api testing",
                "python",
                "jira",
                "postman",
                "jenkins",
                "sql",
                "manual testing",
            ],
            "industries": ["teknoloji", "fintech", "saas"],
            "languages": ["Türkçe", "İngilizce (C1)"],
            "certifications": ["ISTQB Advanced", "Selenium WebDriver"],
            "educations": ["Lisans: Bilgisayar Mühendisliği"],
            "preferred_locations": ["İstanbul", "Remote", "Ankara"],
            "work_modes": ["hybrid", "remote"],
            "salary_expectation": 85000,
            "raw_text": "Ergun Ural - Senior QA & Test Manager CV",
        },
        "weights": {
            "skills_weight": 0.35,
            "experience_weight": 0.25,
            "location_weight": 0.15,
            "salary_weight": 0.10,
            "industry_weight": 0.10,
            "education_weight": 0.05,
        },
        "minimum_match_score": 45.0,
    }
    status, resp = api_call("POST", "/api/v1/watchers", json=payload)
    if status >= 400:
        print(f"  ❌ Watcher create FAILED status={status}")
        print("  ", json.dumps(resp, ensure_ascii=False)[:500])
        return 4
    watcher_id = resp["id"]
    user_id = resp["user_id"]
    print(f"  ✅ Watcher yaratıldı: id={watcher_id}   user_id={user_id}")

    # 2) Delta ölçümü için başlangıç sayıları
    _, pre_runs = api_call("GET", f"/api/v1/watchers/{watcher_id}/runs")
    _, pre_arch = api_call("GET", f"/api/v1/archive/jobs", params={"user_id": user_id})
    pre_n_runs = len(pre_runs) if isinstance(pre_runs, list) else 0
    pre_n_arch = len(pre_arch) if isinstance(pre_arch, list) else 0
    print(f"  [Önce] runs={pre_n_runs}   archives={pre_n_arch}")

    # 3) Discover çağrısı
    disc = {
        "triggered_by": "f10_3_integration_test",
        "max_jobs": 50,
        "source_urls": LI_URLS,
    }
    t0 = time.time()
    print("\n  [3] Discover çağrılıyor (max 50 job)...", flush=True)
    status, resp = api_call("POST", f"/api/v1/watchers/{watcher_id}/discover", json=disc)
    dt = time.time() - t0
    if status >= 400:
        print(f"  ❌ Discover FAILED status={status}")
        print("  ", json.dumps(resp, ensure_ascii=False)[:800])
        return 5
    run = resp.get("run") or {}
    imported = resp.get("imported_jobs") or []
    reports = resp.get("source_reports") or []
    match_scores = []
    for j in imported[:50]:
        ms = j.get("match_score")
        if isinstance(ms, (int, float)):
            match_scores.append(float(ms))
    run_stats = {
        "processed": run.get("processed_jobs", "?"),
        "matched": run.get("matched_jobs", "?"),
        "archived": run.get("archived_jobs", "?"),
        "notified": run.get("notified_jobs", "?"),
        "status": run.get("status"),
        "id": run.get("id"),
    }
    print(f"  ✅ Discover OK · {dt:.1f}s")
    print(f"     Run stats: {run_stats}")
    print(f"     Imported jobs (returned): {len(imported)}")
    print(f"     Source reports: {len(reports)}")
    for r in reports:
        print(f"       · URL: {(r.get('source_url') or '')[:65]}")
        print(f"         status={r.get('status')} jobs={r.get('fetched_jobs')} platform={r.get('source_platform')} note={(r.get('verification_note') or '')[:100]} err={r.get('error_message')!r}")
    if match_scores:
        avg = sum(match_scores) / len(match_scores)
        pct_over50 = 100.0 * sum(1 for s in match_scores if s >= 50.0) / len(match_scores)
        print(f"     Match score: avg={avg:.1f}   median={sorted(match_scores)[len(match_scores)//2]:.1f}   ≥50% = %{pct_over50:.0f}  (örneklem={len(match_scores)})")
        for i, j in enumerate(imported[:5]):
            ms = j.get("match_score")
            title = (j.get("title") or "")[:60]
            company = (j.get("company_name") or "")[:30]
            score_reasons = j.get("match_score_reasons") or []
            print(f"     [{i+1}] %{ms:.0f}  {title!r}  @{company!r}")
            if score_reasons:
                for r in score_reasons[:2]:
                    print(f"            · {str(r)[:100]}")

    # 4) Sonraki delta ölçümü
    _, post_runs = api_call("GET", f"/api/v1/watchers/{watcher_id}/runs")
    _, post_arch = api_call("GET", f"/api/v1/archive/jobs", params={"user_id": user_id})
    post_n_runs = len(post_runs) if isinstance(post_runs, list) else 0
    post_n_arch = len(post_arch) if isinstance(post_arch, list) else 0
    d_runs = post_n_runs - pre_n_runs
    d_arch = post_n_arch - pre_n_arch
    print(f"\n  [Delta] runs: Δ={d_runs:+d}    archives: Δ={d_arch:+d}")

    ok = (
        d_runs >= 1
        and d_arch >= 1
        and len(imported) >= 1
    )
    if match_scores:
        avg_ms = sum(match_scores) / len(match_scores)
        ok = ok and avg_ms >= 50.0
        print(f"  [Match Kalite] avg = %{avg_ms:.0f}   (hedef ≥ %50)")

    print()
    print("=" * 70)
    print(f"SONUÇ: {'✅ F10_3 TAMAM' if ok else '⚠️ Eksik'}  watcher_id={watcher_id}")
    print(f"       Δwatcher_runs = {d_runs:+d}  (hedef ≥ +1)")
    print(f"       Δjob_archives = {d_arch:+d}  (hedef ≥ +1)")
    if match_scores:
        print(f"       avg_match_score = %{sum(match_scores)/len(match_scores):.0f}  (hedef ≥ %50)")
        pct50 = 100.0 * sum(1 for s in match_scores if s >= 50) / len(match_scores)
        print(f"       jobs ≥%50 match = %{pct50:.0f}  ({sum(1 for s in match_scores if s>=50)}/{len(match_scores)})")
    print("=" * 70)
    return 0 if ok else 6


if __name__ == "__main__":
    sys.exit(main())
