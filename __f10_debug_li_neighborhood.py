#!/usr/bin/env python3
"""F10 DEBUG v5: LI Public → absolute job URLs + neighborhood."""
import json
import re
import sys
from pathlib import Path

HTML = Path("/tmp/_li_search.html").read_text(errors="replace")

def main() -> int:
    # 1: Find absolute job URLs
    url_pat = re.compile(r'https?://[a-z]{2,3}\.linkedin\.com/jobs/view/(\d+)[\w\-?&=/.,]*')
    urls = list(url_pat.finditer(HTML))
    print(f"Absolute job URL matches: {len(urls)}")
    # Print neighborhood
    for i, m in enumerate(urls[:6]):
        start = max(0, m.start() - 500)
        end = min(len(HTML), m.end() + 500)
        chunk = HTML[start:end]
        # Strip tag heavy whitespace for readable
        clean = re.sub(r'<[a-zA-Z/][^>]{0,80}>', ' | ', chunk)
        clean = re.sub(r'&[a-z0-9#]{2,10};', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        url = m.group(0)
        jid = m.group(1)
        print(f"\n[{i+1}] Job ID {jid}")
        print(f"  URL: {url[:90]}")
        print(f"  Context (1000 chars): {clean[:1200]}")

    # 2: Find title-like classes visible
    for class_name in ["base-search-card__title", "hidden-nested-link", "base-search-card__subtitle", "job-search-card__location"]:
        c_pat = re.compile(r'class="[^"]*' + re.escape(class_name) + r'[^"]*"[^>]*>([\s\S]{1,120}?)</', re.IGNORECASE | re.DOTALL)
        matches = c_pat.findall(HTML)
        print(f"\nclass='{class_name}' match count: {len(matches)}")
        for txt in matches[:6]:
            txt_c = re.sub(r'<[^>]+>', ' ', txt)
            txt_c = re.sub(r'&[a-z0-9#]{2,10};', '', txt_c)
            txt_c = re.sub(r'\s+', ' ', txt_c).strip()
            if txt_c:
                print(f"   · {txt_c[:100]!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
