#!/usr/bin/env python3
"""F9_4: Boş storage_state iken Scrape Kalite Analizi (KN + YeniBiri, fallback katmanı)"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))
os.chdir(Path(__file__).parent / "apps" / "api")

from app.core.config import get_settings  # noqa: E402
from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402


URLS = [
    ("KariyerNET #1", "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689"),
    ("KariyerNET #2", "https://www.kariyer.net/is-ilanlari?kw=qa+manager&cs=35689"),
    ("YeniBiri  #1", "https://www.yenibiri.com/is-ilanlari?q=test+yoneticisi"),
    ("YeniBiri  #2", "https://www.yenibiri.com/is-ilanlari?q=test+manager"),
]


def main() -> int:
    settings = get_settings()
    storage_path = Path(settings.storage_dir) / "playwright_state.json"
    if storage_path.exists():
        sz = storage_path.stat().st_size
        content = storage_path.read_text()
        print(f"Storage state: {storage_path}")
        print(f"  size bytes = {sz}")
        try:
            d = json.loads(content)
            cookies = d.get("cookies") or []
            origins = d.get("origins") or {}
            print(f"  cookies  = {len(cookies)} adet")
            print(f"  origins  = {len(origins) if isinstance(origins, (list, dict)) else origins!r}")
            if sz <= 40:
                print(f"  ⚠️ BOŞ / cookieless storage_state ({sz} bytes) → fallback katmanı KULLANILACAK")
        except Exception as e:
            print(f"  Parse hatası: {e}")
    else:
        print(f"⚠️ Storage state DOSYA BULUNAMADI: {storage_path}")

    print()
    print("=" * 70)
    print("F9_4: Fallback katmanı ile Scrape Kalite Analizi (cookieless)")
    print("=" * 70)

    service = LiveJobDiscoveryService()

    jobs_total = 0
    reports_by_url: dict[str, object] = {}
    t0 = time.time()

    url_list = [u for _, u in URLS]
    try:
        all_jobs, reports = service.discover(url_list, max_jobs=3 * len(URLS))
    except Exception as exc:
        print(f"❌ discover() exception: {type(exc).__name__}: {exc}")
        return 2

    dt = time.time() - t0
    for r in reports:
        reports_by_url[r.source_url] = r

    jobs_total = len(all_jobs)

    print()
    print(f"Toplam {len(url_list)} URL · {jobs_total} iş ilanı · {dt:.1f}s")
    print()
    print(f"  {'#':>2} {'Site':<14} {'Jobs':>5}  Durum       Platform            URL")
    print(f"  {'-'*2} {'-'*14} {'-'*5}  {'-'*11} {'-'*19} {'-'*50}")
    for idx, (name, url) in enumerate(URLS, 1):
        r = reports_by_url.get(url)
        if r is None:
            print(f"  {idx:>2} {name:<14} {'?':>5}  ❌ Rapor yok  -                   {url[:50]}")
            continue
        platform = str(r.source_platform.value if hasattr(r.source_platform, "value") else r.source_platform) if r.source_platform else "-"
        print(f"  {idx:>2} {name:<14} {r.fetched_jobs:>5}  {r.status:<11} {platform:<19} {url[:50]}")
        note = r.verification_note
        if note:
            print(f"     NOTE: {note[:120]}")

    print()
    print("-" * 70)
    print(f"İlan başına parser regex kapsamı (ilk {min(jobs_total,8)} ilan):")
    regex_coverage = {
        "title": 0,
        "company": 0,
        "location": 0,
        "url": 0,
        "experience": 0,
    }
    for i, job in enumerate(all_jobs[:8], 1):
        pj = job.parsed_job if hasattr(job, "parsed_job") else None
        raw = getattr(pj, "raw_html", "") if pj else ""
        title = getattr(pj, "title", "") or ""
        company = getattr(pj, "company_name", "") or ""
        location = getattr(pj, "location", "") or ""
        url = getattr(pj, "source_url", "") or ""
        meta = getattr(pj, "metadata", {}) or {}
        experience = str(meta.get("experience_years") or meta.get("experience") or "")
        for k, v in [("title", title), ("company", company), ("location", location), ("url", url), ("experience", experience)]:
            if v and str(v).strip():
                regex_coverage[k] += 1
        print(f"  [{i:>2}] {title[:55]:<55}  @{company[:22]:<22}  loc={location[:20]}")

    print()
    print("Parser regex kapsamı (%) — örneklem:")
    n_sample = max(1, min(jobs_total, 8))
    for k, cnt in regex_coverage.items():
        pct = 100.0 * cnt / n_sample
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {k:<12} {cnt}/{n_sample}  {bar}  %{pct:>5.1f}")

    print()
    print("=" * 70)
    print(f"SONUÇ: {jobs_total} job fetched · {len(reports)} report · {dt:.1f}s")
    print(f"       Fallback katmanı (httpx → cloudscraper → Playwright) çalıştı.")
    print("=" * 70)
    return 0 if jobs_total >= 1 else 3


if __name__ == "__main__":
    sys.exit(main())
