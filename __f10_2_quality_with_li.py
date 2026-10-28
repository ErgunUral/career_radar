#!/usr/bin/env python3
"""F10_2: LI Public URL (httpx → JSON-LD fallback → HTML card extract) ile Kalite Testi."""
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
    ("LI #1 - Test Manager TR",  "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0"),
    ("LI #2 - QA Engineer TR",   "https://www.linkedin.com/jobs/search?keywords=QA%20Engineer&location=T%C3%BCrkiye&position=1&pageNum=0"),
    ("LI #3 - Test Otomasyon",   "https://www.linkedin.com/jobs/search?keywords=Test%20Automation&location=T%C3%BCrkiye&position=1&pageNum=0"),
    ("KN  #4 - test yoneticisi", "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689"),
]


def main() -> int:
    print("=" * 70)
    print("F10_2: LinkedIn Public URL + KN URL (httpx + parser FIX) ile Scrape Kalitesi")
    print("=" * 70)

    settings = get_settings()
    storage_path = Path(settings.storage_dir) / "playwright_state.json"
    if storage_path.exists():
        sz = storage_path.stat().st_size
        content = storage_path.read_text()
        print(f"\nStorage state: {storage_path}")
        print(f"  size = {sz} bytes")
        try:
            d = json.loads(content)
            cookies = d.get("cookies") or []
            print(f"  cookies = {len(cookies)}")
            if cookies:
                domains = {}
                for c in cookies:
                    domains[c.get("domain") or "?"] = domains.get(c.get("domain") or "?", 0) + 1
                for dk, n in list(domains.items())[:4]:
                    print(f"    · {dk:<35} {n}")
        except Exception:
            pass

    service = LiveJobDiscoveryService(timeout_seconds=45.0, debug_mode=False)
    t0 = time.time()
    try:
        all_jobs, reports = service.discover(source_urls=[u[1] for u in URLS], max_jobs=100)
    finally:
        try:
            service.close_playwright_pool()
        except Exception:
            pass
    dt = time.time() - t0

    url_to_name = {u[1]: u[0] for _, u in URLS}
    reports_by_url: dict[str, object] = {r.source_url: r for r in reports}

    print(f"\nToplam: {len(URLS)} URL · {len(all_jobs)} job · {dt:.1f}s")
    print()
    print(f"  {'#':>2} {'Site':<22} {'Jobs':>5}  Durum       Platform            URL")
    print(f"  {'-'*2} {'-'*22} {'-'*5}  {'-'*11} {'-'*19} {'-'*55}")
    for idx, (name, url) in enumerate(URLS, 1):
        r = reports_by_url.get(url)
        if r is None:
            print(f"  {idx:>2} {name:<22} {'?':>5}  ❌ Rapor yok  -                   {url[:55]}")
            continue
        sp = r.source_platform
        if hasattr(sp, "value"):
            sp = sp.value
        note = r.verification_note or ""
        url_short = url[:55]
        print(f"  {idx:>2} {name:<22} {r.fetched_jobs:>5}  {r.status:<11} {str(sp or '-'):<19} {url_short}")
        if note:
            print(f"     NOTE: {note[:150]}")

    # Parser coverage (ilk 10 ilan)
    print("\n" + "-" * 70)
    print(f"İlk {min(len(all_jobs), 12)} ilan + parser coverage:")
    coverage = {"title": 0, "company": 0, "location": 0, "url": 0, "platform": 0}
    for i, job in enumerate(all_jobs[:12], 1):
        title = job.title or ""
        company = job.company_name or ""
        loc = job.location or ""
        url = job.source_url or ""
        plat = job.source_platform
        if hasattr(plat, "value"):
            plat = plat.value
        plat = str(plat or "")
        for k, v in [("title", title), ("company", company), ("location", loc), ("url", url), ("platform", plat)]:
            if str(v).strip():
                coverage[k] += 1
        print(f"  [{i:>2}] {title[:62]:<62}  @{company[:24]:<24}  {loc[:20]}")
        if url:
            print(f"       {url[:95]}")

    n_sample = max(1, min(len(all_jobs), 12))
    print(f"\nParser regex kapsamı (örneklem {n_sample}):")
    for k, cnt in coverage.items():
        pct = 100.0 * cnt / n_sample
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {k:<10} {cnt}/{n_sample}  {bar}  %{pct:>5.1f}")

    # URL başına job dağılımı (metadata)
    srcs: dict[str, int] = {}
    for job in all_jobs:
        md = dict(job.metadata or {})
        d_url = md.get("_fetch_url") or md.get("discovery_source_url") or "unknown"
        srcs[d_url] = srcs.get(d_url, 0) + 1

    print(f"\nURL başına job dağılımı:")
    for u, n in list(srcs.items())[:6]:
        nm = url_to_name.get(u, u[:55])
        print(f"  {nm:<25} {n} job")

    ok = len(all_jobs) >= 1
    print("\n" + "=" * 70)
    print(f"SONUÇ: {'✅' if ok else '⚠️'} Toplam job = {len(all_jobs)}")
    print(f"       Coverage title={100*coverage['title']/n_sample:.0f}%  company={100*coverage['company']/n_sample:.0f}%  location={100*coverage['location']/n_sample:.0f}%")
    print("=" * 70)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
