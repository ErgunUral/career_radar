#!/usr/bin/env python3
"""F9: Helper — HTTP ile Watcher OLUŞTUR (API server DB'sine)."""
import json
import sys
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api/v1"
OUT_WID = Path("/tmp/_f9_wid.txt")


def main() -> int:
    profile = {
        "headline": "Test Yöneticisi / QA Manager / Kalite Güvence Lideri",
        "summary": "15+ yıl yazılım test ve kalite güvence deneyimi. Manuel/otomasyon test stratejisi, ekip yönetimi, CI/CD entegrasyonu.",
        "total_experience_years": 15.0,
        "management_years": 8.0,
        "team_size_managed": 12,
        "skills": ["Selenium", "Cypress", "Playwright", "Postman", "JMeter", "TestRail", "JIRA", "SQL", "Python", "Java", "CI/CD", "Agile", "Scrum", "API Test", "Performance Test", "Regression Test"],
        "industries": ["Fintech", "Bilişim", "E-Ticaret", "SaaS"],
        "languages": ["Türkçe (Anadil)", "İngilizce (İleri - C1)"],
        "certifications": ["ISTQB Advanced", "CSM", "AWS Cloud Practitioner"],
        "educations": ["Lisans - Bilgisayar Mühendisliği"],
        "preferred_locations": ["İstanbul", "Ankara", "İzmir", "Remote", "Hibrit"],
        "work_modes": ["remote", "hybrid", "onsite"],
    }
    body = {
        "user_id": "user-ergun",
        "query_name": "Gerçek Test Yöneticisi / QA Lideri (F9)",
        "source_platform": "linkedin_search_url",
        "candidate_profile": profile,
        "search_criteria": {
            "keywords": ["Test Yöneticisi", "QA Manager", "Test Manager"],
            "locations": ["İstanbul", "Remote"],
            "min_experience_years": 5,
        },
        "minimum_match_score": 55.0,
        "sync_frequency_minutes": 120,
        "is_active": True,
    }
    print("POST /watchers → (API server DB = apps/api/careerradar.db)")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    try:
        client = httpx.Client(timeout=90)
        r = client.post(API + "/watchers", json=body, headers=headers)
    except Exception as e:
        print(f"  HATA: {type(e).__name__}: {e}")
        return 2
    print(f"  HTTP {r.status_code}")
    if r.status_code >= 400:
        print(f"  {r.text[:1200]}")
        return 1
    w = r.json()
    wid = w["id"]
    OUT_WID.write_text(wid)
    print(f"  ✅ Watcher ID: {wid}")
    print(f"     name      : {w.get('query_name')}")
    print(f"     user_id   : {w.get('user_id')}")
    print(f"     min_score : {w.get('minimum_match_score')}")
    print(f"     is_active : {w.get('is_active')}")

    print()
    print("GET /watchers doğrulama:")
    r2 = client.get(API + "/watchers", headers={"Accept": "application/json"})
    print(f"  HTTP {r2.status_code} · count = {len(r2.json()) if r2.status_code == 200 else '?'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
