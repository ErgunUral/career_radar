#!/usr/bin/env python3
"""F10_3 helper: Mevcut durumu ölç (API çağrıları)."""
import json
import sys

import httpx

API = "http://localhost:8000"
WID = "watcher-45dfca0a6f84"
UID = "user-ergun"

def get(p, **kw):
    r = httpx.get(API + p, timeout=30, **kw)
    return r.status_code, r.json()

_, d = get(f"/api/v1/watchers/{WID}/runs")
print(f"Runs count: {len(d)}")
for r in d:
    print(f"  id={r.get('id')}  status={r.get('status')}  processed={r.get('processed_jobs')}  matched={r.get('matched_jobs')}  archived={r.get('archived_jobs')}")
    md = r.get("metadata") or {}
    if "inactive_jobs_skipped" in md:
        print(f"     inactive_skipped={md['inactive_jobs_skipped']}")
    if "source_reports" in md:
        for sr in md["source_reports"][:3]:
            url = (sr.get("source_url") or "")[:55]
            print(f"     sr: {url} status={sr.get('status')} jobs={sr.get('fetched_jobs')} err={(sr.get('error_message') or '')[:80]}")

_, d = get("/api/v1/archive/jobs", params={"user_id": UID})
print(f"\nArchive count: {len(d)}")
for a in d[:8]:
    t = (a.get("job_title") or "")[:55]
    ms = a.get("match_score")
    c = (a.get("company_name") or "")[:25]
    print(f"  %{str(ms):<5}  {t!r}  @{c!r}")
