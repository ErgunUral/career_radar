#!/usr/bin/env python3
"""F10 DEBUG: Niçin svc._fetch_html_with_fallback httpx katmanında 4XX veriyor?"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))
import httpx

from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402


URL = "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0"

svc = LiveJobDiscoveryService(timeout_seconds=45)

print("=== svc._headers_for(URL) ===")
hdrs = dict(svc._headers_for(URL))
for k, v in hdrs.items():
    print(f"  {k}: {v[:120]}")

print("\n=== 1) httpx.get(URL) with svc headers ===")
try:
    r = httpx.get(URL, timeout=45, follow_redirects=True, headers=hdrs)
    print(f"  status = {r.status_code}")
    print(f"  len(text) = {len(r.text)}")
    print(f"  data-entity-urn count = {len(re.findall(r'data-entity-urn=\"urn:li:jobPosting:\\d+', r.text))}")
    if r.status_code != 200 or len(r.text) < 5000:
        print(f"  first 1500 chars: {r.text[:1500]!r}")
except Exception as e:
    print(f"  EXC: {type(e).__name__}: {e}")

print("\n=== 2) httpx.get(URL) DEFAULT headers (sadece UA) ===")
def_hdrs = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
try:
    r = httpx.get(URL, timeout=45, follow_redirects=True, headers=def_hdrs)
    print(f"  status = {r.status_code}")
    print(f"  len(text) = {len(r.text)}")
    print(f"  data-entity-urn count = {len(re.findall(r'data-entity-urn=\"urn:li:jobPosting:\\d+', r.text))}")
except Exception as e:
    print(f"  EXC: {type(e).__name__}: {e}")

print("\n=== 3) svc._fetch_html_with_fallback chain details (adım adım) ===")
# Katman 1: httpx (normal)
headers1 = dict(svc._headers_for(URL))
timeout1 = 45
print("  [Katman 1: httpx] çağrılıyor...")
try:
    r1 = httpx.get(URL, timeout=timeout1, follow_redirects=True, headers=headers1)
    st1 = int(r1.status_code or 0)
    ct1 = r1.headers.get("content-type", "") or ""
    bt1 = r1.text or ""
    print(f"    status={st1} len={len(bt1)} ct={ct1[:60]!r}")
    good1 = 200 <= st1 < 300 and len(bt1) > 5000
    print(f"    [Katman 1] başarılı mı? {good1}")
except Exception as e1:
    print(f"    Exception: {type(e1).__name__}: {e1}")
    st1 = 0; ct1 = ""; bt1 = ""; good1 = False

# Katman 2: cloudscraper (mevcutsa)
print("  [Katman 2: cloudscraper] deneniyor...")
try:
    import cloudscraper  # type: ignore
    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "ios", "desktop": True})
    r2 = scraper.get(URL, timeout=timeout1, headers=headers1)
    st2 = int(r2.status_code or 0)
    ct2 = r2.headers.get("content-type", "") or ""
    bt2 = r2.text or ""
    print(f"    status={st2} len={len(bt2)} ct={ct2[:60]!r}")
    good2 = 200 <= st2 < 300 and len(bt2) > 5000
    print(f"    [Katman 2] başarılı mı? {good2}")
except Exception as e2:
    print(f"    Exception: {type(e2).__name__}: {e2}")
    st2 = 0; ct2 = ""; bt2 = ""; good2 = False

svc.close_playwright_pool()
