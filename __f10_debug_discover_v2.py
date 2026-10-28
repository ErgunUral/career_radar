#!/usr/bin/env python3
"""F10 DEBUG: Discover() niçin hala Playwright zorluyor? Tüm akışı tek tek adımla."""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

from app.domains.watchers.discovery import (  # noqa: E402
    LiveJobDiscoveryService,
    JobSourcePlatform,
)

URL = "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0"

svc = LiveJobDiscoveryService(timeout_seconds=45)

print("=== ADIM 1: URL Sınıflandırma ===")
parsed = urlparse(URL)
print(f"  netloc = {parsed.netloc!r}   path = {parsed.path!r}")
plat = svc._infer_source_platform(URL)
print(f"  _infer_source_platform(URL) = {plat}")

print("\n=== ADIM 2: Force Playwright kontrolü ===")
host = parsed.netloc.casefold().strip()
path_q = (parsed.path or "") + "?" + (parsed.query or "")
print(f"  host (casefold) = {host!r}")
print(f"  /jobs/search in path_q = {'/jobs/search' in path_q.casefold()}")
print(f"  host in _DOMAINS_FORCE_PLAYWRIGHT = {host in svc._DOMAINS_FORCE_PLAYWRIGHT}")
parts = host.split(".")
parent = ".".join(parts[-2:]) if len(parts) >= 2 else ""
print(f"  parent domain = {parent!r}   in list? {parent in svc._DOMAINS_FORCE_PLAYWRIGHT}")
print(f"  svc._should_force_playwright(URL) = {svc._should_force_playwright(URL)}")

print("\n=== ADIM 3: Direct _fetch_html_with_fallback (SONUC) ===")
st, body, ct, fm = svc._fetch_html_with_fallback(URL, allow_playwright=True)
print(f"  status = {st}  content-type = {ct[:60]!r}  fetch_method = {fm!r}")
print(f"  len(body) = {len(body)} bytes")
print(f"  body'de data-entity-urn/jobPosting var mı? {bool('data-entity-urn' in body and 'jobPosting' in body)}")

print("\n=== ADIM 4: Discover SOURCE URL flow — URL'leri doğru şekilde geçirelim ===")
print(f"  DISCOVER: source_urls=[{URL[:80]}...]  max_jobs=20")
try:
    jobs, reports = svc.discover(source_urls=[URL], max_jobs=20)
    print(f"  len(jobs)={len(jobs)}  len(reports)={len(reports)}")
    for r in reports:
        print(f"  Rapor: status={r.status} jobs={r.jobs_found} src={r.source_id} platform={r.source_platform}")
        print(f"         error={r.error_message!r}")
        print(f"         note={r.note!r}")
    if jobs:
        for j in jobs[:5]:
            print(f"  JOB: {j.title[:55]!r}  @{j.company_name[:30]!r}  {j.location[:25]!r}")
except Exception as e:
    import traceback
    print(f"  HATA: {type(e).__name__}: {e}")
    traceback.print_exc()
finally:
    svc.close_playwright_pool()
