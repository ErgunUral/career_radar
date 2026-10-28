#!/usr/bin/env python3
"""F9 Helper: Watcher PATCH source_urls ekle + kontrol et."""
import json
import sys
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api/v1"
WID_FILE = Path("/tmp/_f9_wid.txt")


def main() -> int:
    wid = Path("/tmp/_f9_wid.txt").read_text().strip() if WID_FILE.exists() else sys.argv[1]
    print(f"Watcher ID = {wid}")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    patch_body = {
        "search_criteria": {
            "keywords": ["Test Yöneticisi", "QA Manager", "Test Manager"],
            "locations": ["İstanbul", "Remote"],
            "min_experience_years": 5,
            "source_urls": [
                "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689",
                "https://www.kariyer.net/is-ilanlari?kw=qa+manager&cs=35689",
                "https://www.yenibiri.com/is-ilanlari?q=test+yoneticisi",
                "https://www.yenibiri.com/is-ilanlari?q=test+manager",
            ],
        },
        "minimum_match_score": 50.0,
        "is_active": True,
    }

    client = httpx.Client(timeout=60)
    print(f"PATCH /watchers/{wid} → search_criteria.source_urls={len(patch_body['search_criteria']['source_urls'])} URL")
    r = client.patch(API + f"/watchers/{wid}", json=patch_body, headers=headers)
    print(f"  HTTP {r.status_code}")
    if r.status_code >= 400:
        print(r.text[:1000])
        return 1
    w = r.json()
    src_urls = (w.get("search_criteria") or {}).get("source_urls") or []
    print(f"  ✅ Güncellendi: search_criteria.source_urls len = {len(src_urls)}")
    for u in src_urls[:5]:
        print(f"     · {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
