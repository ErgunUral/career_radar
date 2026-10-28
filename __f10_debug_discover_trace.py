#!/usr/bin/env python3
"""F10 DEBUG: Discover traceback + direct _extract_linkedin_jobs test."""
import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))
os.chdir(Path(__file__).parent / "apps" / "api")

import httpx  # noqa: E402
from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402


URL = "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main() -> int:
    print("=" * 70)
    print("F10 DEBUG: Discover + direct extract test")
    print("=" * 70)

    # 1) Direct httpx get → body
    print("\n[1] httpx GET →", URL[:70])
    t0 = time.time()
    r = httpx.get(URL, timeout=45.0, follow_redirects=True, headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.6"})
    dt = time.time() - t0
    print(f"   HTTP {r.status_code} · {len(r.content)//1024} KB · {dt:.1f}s")

    # 2) Direct _extract_linkedin_jobs çağrısı (manually)
    print("\n[2] Direct svc._extract_linkedin_jobs:")
    svc = LiveJobDiscoveryService(timeout_seconds=45.0)
    try:
        jobs = svc._extract_linkedin_jobs(r.text or "", URL)
    except Exception:
        traceback.print_exc()
        jobs = []
    print(f"   Sonuç: {len(jobs)} job")
    for i, j in enumerate(jobs[:8], 1):
        print(f"   [{i}] {j.title[:65]!r}  @{j.company_name[:25]!r}  {j.location[:22]!r}")
        print(f"        {j.source_url[:90]}")

    # 3) Discover ile birebir aynı
    print(f"\n[3] svc.discover(source_urls=[LI URL], max_jobs=20):")
    try:
        all_jobs, reports = svc.discover(source_urls=[URL], max_jobs=20)
    except Exception:
        traceback.print_exc()
        all_jobs, reports = [], []
    print(f"   len(jobs)={len(all_jobs)}  len(reports)={len(reports)}")
    for r in reports:
        note = r.verification_note or ""
        err = r.error_message or ""
        print(f"   · status={r.status} jobs={r.fetched_jobs} src_plat={r.source_platform}")
        if note:
            print(f"     note: {note[:120]}")
        if err:
            print(f"     err: {err[:120]}")

    # 4) storage_state kontrol
    try:
        svc.close_playwright_pool()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
