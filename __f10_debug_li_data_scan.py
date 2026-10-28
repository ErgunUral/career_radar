#!/usr/bin/env python3
"""F10 DEBUG v4: LinkedIn Public HTML → embedded job data (window + href etrafı)"""
import json
import re
import sys
from pathlib import Path

import httpx

HTML_FILE = Path("/tmp/_li_search.html")
URL = "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&position=1&pageNum=0"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main() -> int:
    if not HTML_FILE.exists() or HTML_FILE.stat().st_size < 10000:
        print(f"httpx GET → {URL}")
        r = httpx.get(URL, timeout=45.0, follow_redirects=True, headers={
            "User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.6"})
        print(f"  HTTP {r.status_code} · {len(r.content)//1024} KB")
        HTML_FILE.write_bytes(r.content or b"")
    html = HTML_FILE.read_text(errors="replace")
    print(f"HTML: {len(html)} chars")

    print("\n[1] Script tagları window.* JSON / array:")
    script_pat = re.compile(r'<script[^>]*>([\s\S]{1000,}?)</script>', re.IGNORECASE)
    for i, s in enumerate(script_pat.findall(html)):
        # window.*= gibi başlangıçlar
        wpat = re.compile(r'window\.\s*([\w$]+)\s*=\s*(\{[\s\S]{100,}?\}|\[[\s\S]{100,}?\])\s*;?\s*$', re.MULTILINE)
        for m in wpat.finditer(s):
            key = m.group(1)
            raw = m.group(2).strip()
            try:
                d = json.loads(raw)
                n = len(d) if isinstance(d, (list, dict)) else 0
                fp = f"/tmp/_li_win_{key}.json"
                Path(fp).write_text(json.dumps(d, indent=2, ensure_ascii=False))
                print(f"  window.{key:<30} OK → {fp} ({len(raw)//1024}KB)  size={n}")
                # job referansları aramak için
                terms = ("job_id", "jobId", "job_title", "jobTitle", "title", "company", "hiringOrg")
                def walk(o, d2=0):
                    if d2 > 8: return
                    if isinstance(o, dict):
                        ks = o.keys()
                        mtch = [k for k in ks if any(t.lower() in str(k).lower() for t in terms)]
                        if mtch and d2 <= 4:
                            print(f"    job keys ({d2}.depth): {mtch[:8]}")
                            print(f"    sample: title={str(o.get('title',''))[:70]!r} company={str(o.get('company',''))[:40]!r}")
                        for v in o.values(): walk(v, d2+1)
                    elif isinstance(o, list):
                        for item in o[:30]: walk(item, d2+1)
                walk(d)
            except Exception as exc:
                # window.* = await Promise.resolve(..) gibisinden olabilir, JSON parse edemeyiz
                pass

    # 2: `<base-card>` veya `<li class="result-card">` HTML elementleri (classları)
    print("\n[2] HTML job card / result-item elementleri:")
    pats = [
        ('li class="result-card"', r'<li[^>]*class="[^"]*result-card[^"]*"[\s\S]*?</li>'),
        ('div class="base-card"',  r'<div[^>]*class="[^"]*base-card[^"]*"[\s\S]*?</div>'),
        ('class="job-result-card"', r'class="[^"]*job-result-card[^"]*"'),
        ('data-id / data-job-id',  r'data-job-id=["\'](\d+)["\']'),
        ('href="/jobs/view/'     ,  r'href=["\'](/jobs/view/\d+)[^"\']*["\']([^>]*)>'),
    ]
    for name, pat in pats:
        ms = list(re.finditer(pat, html, re.IGNORECASE))
        print(f"  {name:<28} → {len(ms)} match")
        if ms and name.startswith("href="):
            for i, m in enumerate(ms[:5]):
                href = m.group(1)
                rest = m.group(2)
                # arkasından metin çıkar
                text_m = re.search(r'>([^<]{5,80})<', m.group(0))
                print(f"    · {href:<40}  → txt={text_m.group(1).strip() if text_m else ''!r}")
    # 3: A href etrafında komşu elementlerde title/company bul (200 char neighborhood)
    print("\n[3] href=/jobs/view/ neighborhood (200 char lookaround):")
    found = 0
    for m in re.finditer(r'href=["\']?(/jobs/view/\d+)([^"\'>]*["\']?)', html):
        if found >= 5: break
        start = max(0, m.start()-200)
        end = min(len(html), m.end()+300)
        neigh = html[start:end]
        # temiz text
        txt = re.sub(r'<[^>]+>', ' | ', neigh)
        txt = re.sub(r'\s+', ' ', txt).strip()
        job_id_m = re.search(r'/jobs/view/(\d+)', neigh)
        job_id = job_id_m.group(1) if job_id_m else "?"
        print(f"  job#{job_id}: {txt[:180]}")
        found += 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
