#!/usr/bin/env python3
"""F10 DEBUG: 2 sorunun izahı + regex pattern test."""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

import httpx
from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402


URL = "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0"
HTML_FILE = Path("/tmp/_li_search.html")


def main() -> int:
    # 1) URL netloc + _should_force_playwright HATA test
    parsed = urlparse(URL)
    host = parsed.netloc.casefold().strip()
    path_q = (parsed.path or "") + "?" + (parsed.query or "")
    print(f"[1] URL parse test:")
    print(f"    host     = {host!r}")
    print(f"    path+q   = {path_q[:80]!r}")
    print(f"    host in _DOMAINS_FORCE_PLAYWRIGHT = {host in LiveJobDiscoveryService._DOMAINS_FORCE_PLAYWRIGHT}")
    svc = LiveJobDiscoveryService()
    print(f"    svc._should_force_playwright(URL) = {svc._should_force_playwright(URL)}")
    # Neden force döndü? İçeride: www.linkedin.com listede VAR → ilk return True'dan çıkıyor,
    # "/jobs/search" kontrolüne ulaşamıyor. BUG!
    print()

    # 2) Direct split pattern test
    html = HTML_FILE.read_text(errors="replace")
    print(f"[2] Split pattern test (HTML {len(html)} chars):")
    split_pat = re.compile(r'<\w[^>]*\sclass="[^"]*base-card[^"]*"[^>]*>')
    segs = split_pat.split(html)
    print(f"    segments (toplam) = {len(segs)} (split sonrası)")
    # İlk 5 segment boyutları
    for i, s in enumerate(segs[:6]):
        print(f"      seg[{i}] len={len(s)}  title class var mı? {bool(re.search(r'base-search-card__title', s))}   hidden-nested-link? {bool(re.search(r'hidden-nested-link', s))}")

    # Title pattern test (tek tek class count ile önceki bulduğumuz 60 karşılaştır)
    title_pat = re.compile(r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</', re.IGNORECASE | re.DOTALL)
    titles = title_pat.findall(html)
    print(f"\n    doğrudan base-search-card__title regex findall = {len(titles)}")
    for t in titles[:4]:
        t_clean = re.sub(r'<[^>]+>', ' ', t).strip()
        print(f"      · {t_clean!r}")

    # 3) Neden direct _extract_linkedin_jobs 0 job? Segment 1+ test edelim
    print(f"\n[3] Direct _extract_linkedin_jobs test:")
    jobs = svc._extract_linkedin_jobs(html, URL)
    print(f"    sonuç = {len(jobs)} job")
    if jobs:
        for j in jobs[:5]:
            print(f"      · {j.title[:55]!r}  @{j.company_name[:25]!r}  {j.location[:20]!r}")
    else:
        # Segment 1-2 ara ayrıntılı
        if len(segs) >= 2:
            seg1 = segs[1][:5000]
            # Hangi pattern eksik?
            has_url_abs = bool(re.search(r'href="https?://[^"]*/jobs/view/[^"]+"', seg1))
            has_url_rel = bool(re.search(r'href="/jobs/view/[^"]+"', seg1))
            has_title = bool(re.search(r'base-search-card__title[^>]*>(.*?)</', seg1, re.DOTALL))
            has_company_hidden = bool(re.search(r'hidden-nested-link[^>]*>(.*?)</', seg1, re.DOTALL))
            print(f"    seg[1] (5000 chars):")
            print(f"      abs href /jobs/view/  = {has_url_abs}")
            print(f"      rel href /jobs/view/  = {has_url_rel}")
            print(f"      base-search-card__title class = {has_title}")
            print(f"      hidden-nested-link class = {has_company_hidden}")
            if not (has_url_abs or has_url_rel):
                print("      ⚠️ URL pattern MATCH ETMİYOR → yeni URL pattern araştır")
                # segment 1 de href olan patternları çıkar
                hrefs = re.findall(r'href="([^"]{10,100})"', seg1)
                print(f"      örnek hrefs (seg1): {hrefs[:8]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
