#!/usr/bin/env python3
"""F10 DEBUG v3: LinkedIn Public search page (unauth) → JSON-LD JobPosting test."""
import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402

URLS = [
    ("LI Public Test Manager TR", "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0"),
    ("LI Public QA Engineer TR",  "https://www.linkedin.com/jobs/search?keywords=QA%20Engineer&location=T%C3%BCrkiye&position=1&pageNum=0"),
    ("KN search test yoneticisi", "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689"),
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main() -> int:
    print("=" * 70)
    print("F10 DEBUG v3: LinkedIn Public JSON-LD vs KN")
    print("=" * 70)
    client = httpx.Client(timeout=45.0, follow_redirects=True, headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.6"})
    svc = LiveJobDiscoveryService(timeout_seconds=45.0, debug_mode=False)

    for name, url in URLS:
        t0 = time.time()
        try:
            r = client.get(url)
        except Exception as e:
            print(f"\n[{name}] HATA: {type(e).__name__}: {e!s}")
            continue
        dt = time.time() - t0
        html = r.text or ""
        body_bytes = len(r.content or b"")
        title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = (title_m.group(1).strip()[:75]) if title_m else ""
        print(f"\n[{name}]")
        print(f"   HTTP {r.status_code} · {body_bytes//1024}KB · {dt:.1f}s · title={title!r}")

        # JSON-LD JobPosting sayısı (manuel sayım)
        count_jobposting = len(re.findall(r'"@type"\s*:\s*"JobPosting"', html))
        count_card_links = len(re.findall(r"/jobs/view/|jobs/view/\d+", html))
        print(f"   \"@type\":\"JobPosting\" count = {count_jobposting}")
        print(f"   /jobs/view/ link count        = {count_card_links}")

        # Doğrudan servis katmanındaki extract metodu çağır (json-ld)
        jobs_ld = svc._extract_from_json_ld(html, url)
        print(f"   _extract_from_json_ld → {len(jobs_ld)} job")
        for i, j in enumerate(jobs_ld[:5], 1):
            title = j.title or ""
            company = j.company_name or ""
            loc = j.location or ""
            print(f"     [{i}] {title[:65]:<65}  @{company[:28]:<28}  {loc[:20]}")
            if j.source_url:
                print(f"          {j.source_url[:80]}")

        # Genel fallback (toplam)
        all_jobs = svc._extract_jobs(url, r.headers.get("content-type", ""), html)
        print(f"   _extract_jobs TOTAL → {len(all_jobs)} job")

    try:
        client.close()
    except Exception:
        pass
    try:
        svc.close_playwright_pool()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
