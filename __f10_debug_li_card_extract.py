#!/usr/bin/env python3
"""F10 DEBUG v5: LI base-card → regex ile title/company/location/href çıkar."""
import json
import re
import sys
from pathlib import Path

HTML = Path("/tmp/_li_search.html").read_text(errors="replace")

def main() -> int:
    # base-card div (60 tane)
    card_pat = re.compile(r'<div[^>]*class="([^"]*base-card[^"]*)"[^>]*>([\s\S]{200,}?)</div>\s*</div>', re.IGNORECASE)
    cards = list(card_pat.finditer(HTML))
    print(f"base-card iterator count: {len(cards)}")

    # Gerçek href desenleri (absolute hrefler / absolute URL:
    for i = 0
    href_pat_abs = re.compile(r'href=["\'](https?://[^"\']*linkedin\.com/jobs/view/(\d+)[^"\']*)["\']')
    href_pat_rel = re.compile(r'href=["\'](/jobs/view/(\d+)[^"\']*)["\']')
    title_pat = re.compile(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>\s*([^<]+?")\s]*)<')
    company_pat = re.compile(r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>\s*([^<]{3,100}\s*<')
    location_pat = re.compile(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>\s*([^<"]{2,80}?)\s*<')
    # Simple approach: extract absolute URL (any job URL)
    jobs: list[dict] = []
    for m in re.finditer(r'(https://[a-z]{2,3}\.linkedin\.com/jobs/view/(\d+)[\w\-?&=/]*?)["\']', HTML, re.IGNORECASE):
        if i >= 12: break
        url = m.group(1)
        jid = m.group(2)
        start = max(0, m.start()-500)
        end = min(len(HTML), m.end()+500)
        chunk = HTML[start:end]
        # cleanup HTML tag strip
        # title
        t_m = re.search(r'<h3[^>]*>([\s\S]{1,120}?</h3>', chunk)
        title = ""
        if t_m:
            title = re.sub(r'<[^>]+>', ' ', t_m.group(0)).strip()[:120]
        c_m = re.search(r'<h4[^>]*>([\s\S]{1,150}?</h4>', chunk)
        company = ""
        if c_m:
            company = re.sub(r'<[^>]+>', ' ', c_m.group(0)).strip()[:80]
        loc_m = re.search(r'(job-search-card__location[^>]*>([\s\S]{1,150}?</span>', chunk, re.IGNORECASE)
        location = ""
        if loc_m:
            location = re.sub(r'<[^>]+>', ' ', loc_m.group(0)).strip()[:80]
        if title or company or location:
            jobs.append({"id": jid, "title": title, "company": company, "location": location, "url": url})
            print(f"[{i+1:>2}] j#{jid} {title[:70:<70!r}")
            print(f"     @{company!r}  {location!r}")
            print(f"     url: {url[:90]}")
            i += 1
    print()
    print(f"Extracted {len(jobs)} jobs from raw HTML.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
