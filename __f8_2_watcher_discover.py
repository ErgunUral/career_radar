#!/usr/bin/env python3
"""Faz 8_2: Gerçek Watcher oluştur + Discover tetikle + Archive INSERT doğrula."""
import json
import sys
import urllib.request
import urllib.error
import time
from pathlib import Path

API = "http://127.0.0.1:8000/api/v1"
USER = "user-ergun"
OUT_WID = Path("/tmp/_fw_wid.txt")


def http(method, path, body=None, timeout=600):
    import httpx
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body, ensure_ascii=False)
    try:
        client = httpx.Client(timeout=timeout)
        if method == "GET":
            r = client.get(API + path, headers=headers, params=body if isinstance(body, dict) else None)
        else:
            r = client.request(method, API + path, headers=headers, content=body if isinstance(body, str) else None, json=body if isinstance(body, (dict, list)) else None)
        return r.status_code, r.json() if r.text else None
    except httpx.HTTPStatusError as e:
        try:
            payload = e.response.json()
        except Exception:
            payload = {"raw": str(e)}
        return e.response.status_code, payload
    except Exception as e:
        return 500, {"error": type(e).__name__, "msg": str(e)[:300]}


def main():
    print("=" * 70)
    print("FAZ 8_2: Gerçek Watcher + Discover + Archive Doğrulama")
    print("=" * 70)

    # 1. Watcher oluştur
    profile = {
        "headline": "Test Yöneticisi / QA Manager / Kalite Güvence Lideri",
        "summary": "15+ yıl yazılım test ve kalite güvence deneyimi. Manuel/otomasyon test stratejisi, ekip yönetimi, CI/CD entegrasyonu.",
        "total_experience_years": 15.0,
        "management_years": 8.0,
        "team_size_managed": 12,
        "skills": ["Selenium", "Cypress", "Playwright", "Postman", "JMeter", "TestRail", "JIRA", "SQL", "Python", "Java", "CI/CD", "Agile", "Scrum", "API Test", "Performance Test", "Regression Test"],
        "industries": ["Fintech", "Bilişim", "E-Ticaret", "SaaS"],
        "languages": ["Türkçe (Anadil)", "İngilizce (İleri - C1)"],
        "certifications": ["ISTQB Advanced", "CSM (Certified Scrum Master)", "AWS Cloud Practitioner"],
        "educations": ["Lisans - Bilgisayar Mühendisliği"],
        "preferred_locations": ["İstanbul", "Ankara", "İzmir", "Remote", "Hibrit"],
        "work_modes": ["remote", "hybrid", "onsite"],
    }
    create_body = {
        "user_id": USER,
        "query_name": "Gerçek Test Yöneticisi / QA Lideri",
        "source_platform": "linkedin_search_url",
        "candidate_profile": profile,
        "search_criteria": {
            "keywords": ["Test Yöneticisi", "QA Manager", "Test Manager", "Kalite Güvence Müdürü"],
            "locations": ["İstanbul", "Ankara", "İzmir", "Remote"],
            "min_experience_years": 5,
        },
        "minimum_match_score": 55.0,
        "sync_frequency_minutes": 120,
        "is_active": True,
    }
    print("\n[1/5] Watcher oluşturuluyor (POST /watchers)...")
    st, w = http("POST", "/watchers", create_body)
    if st >= 400 or not w.get("id"):
        print(f"HATA: HTTP {st}: {json.dumps(w, ensure_ascii=False, indent=2)}")
        return 1
    wid = w["id"]
    OUT_WID.write_text(wid)
    print(f"  ✅ OK HTTP {st}")
    print(f"    id        = {wid}")
    print(f"    name      = {w.get('query_name')}")
    print(f"    user_id   = {w.get('user_id')}")
    print(f"    min_score = {w.get('minimum_match_score')}")
    print(f"    is_active = {w.get('is_active')}")

    # 2. Gerçek 2 kaynak URL: KN + YeniBiri (LinkedIn 999 döndüğü için sona)
    urls = [
        "https://www.kariyer.net/is-ilanlari?k=Test+Yoneticisi",
        "https://www.yenibiris.com/is-ilanlari?k=Test+Yonetici",
    ]
    print("\n[2/5] 2 Gerçek Kaynak URL hazırlandı:")
    for i, u in enumerate(urls, 1):
        print(f"    {i}. {u[:100]}")

    # 3. POST /watchers/{id}/discover
    print(f"\n[3/5] POST /watchers/{wid}/discover tetikleniyor (max_jobs=10, timeout 600s)...")
    discover_body = {"source_urls": urls, "max_jobs": 10, "triggered_by": "faz8-manual"}
    t0 = time.time()
    st, dr = http("POST", f"/watchers/{wid}/discover", discover_body, timeout=180)
    elapsed = time.time() - t0
    print(f"  HTTP {st} · Süre: {elapsed:.1f}s")
    if st >= 400:
        print(f"HATA: {json.dumps(dr, ensure_ascii=False, indent=2)[:800]}")
        return 2
    # Raporları yazdır
    print(f"  run_id           = {dr.get('run_id')}")
    print(f"  discovered_raw   = {dr.get('discovered_jobs_count', 0)}")
    print(f"  archived         = {len(dr.get('archived_jobs') or [])}")
    print(f"  notifications    = {dr.get('notifications_created_count', 0)}")
    reports = dr.get("source_reports") or []
    print(f"  kaynak raporu    = {len(reports)} adet")
    for r in reports:
        print(f"    - [{r.get('status','?')}] jobs={r.get('fetched_jobs',0)}  {str(r.get('source_url',''))[:90]}")

    # 4. GET /archive
    print(f"\n[4/5] GET /archive?user_id={USER} kontrol...")
    st, archives = http("GET", f"/archive?user_id={USER}&limit=20")
    print(f"  HTTP {st} · Archive kayıt sayısı = {len(archives)}")
    if archives:
        print("  İlk 5 arşiv:")
        for a in archives[:5]:
            score = a.get('match_score') or 0
            co = a.get('company') or '?'
            title = (a.get('title') or '')[:70]
            src = a.get('source_url') or ''
            print(f"    id={a['id']} score=%{score:.0f} @{co[:30]:<30} | {title}")
            if src:
                print(f"      {src[:110]}")
    else:
        print("  ⚠️  Henüz arşive alınan iş yok (score < min_score veya boş döndü).")

    # 5. GET /logs (son 15 kayıt)
    print(f"\n[5/5] GET /logs (son 15 kayıt, user_id={USER} OR NULL) — kaynak/seviye dağılımı:")
    st, logs = http("GET", f"/logs?limit=15&user_id={USER}")
    levels, sources = {}, {}
    for l in logs:
        levels[l["level"]] = levels.get(l["level"], 0) + 1
        sources[l["source"]] = sources.get(l["source"], 0) + 1
    print(f"  HTTP {st} · Toplam = {len(logs)}")
    print(f"  Seviye  : {levels}")
    print(f"  Kaynak  : {sources}")
    # Son 5 log satırı
    print("  Son 5 log:")
    for l in logs[-5:]:
        uid = l.get('user_id') or '-'
        src = l.get('source') or '?'
        lvl = l.get('level') or '?'
        msg = (l.get('message') or '')[:90]
        print(f"    [{lvl:<5}] {src:<10} u={uid:<12} | {msg}")

    print("\n" + "=" * 70)
    print("✅ Faz 8_2 Tamamlandı.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
