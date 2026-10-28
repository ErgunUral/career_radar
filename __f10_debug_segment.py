#!/usr/bin/env python3
"""F10 DEBUG: İlk 6 segmentin detayları + URL pattern debug."""
import json
import re
import sys
from pathlib import Path

HTML = Path("/tmp/_li_search.html").read_text(errors="replace")

split_pat = re.compile(r'<\w[^>]*\sclass="[^"]*base-card[^"]*"[^>]*>')
segs = split_pat.split(HTML)

for i in range(min(8, len(segs))):
    s = segs[i][:3000]
    print(f"\n== Seg[{i}] (top 3000 / {len(segs[i])} chars) ==")
    # Bul: title/company/location/url
    title = re.search(r'class="[^"]*base-search-card__title[^"]*"[^>]*>([\s\S]{1,100}?)</', s, re.IGNORECASE)
    company = re.search(r'class="[^"]*hidden-nested-link[^"]*"[^>]*>([\s\S]{1,100}?)</', s, re.IGNORECASE)
    location = re.search(r'class="[^"]*job-search-card__location[^"]*"[^>]*>([\s\S]{1,80}?)</', s, re.IGNORECASE)
    hrefs = re.findall(r'href=([\'"])([^\1]{10,120})\1', s, re.IGNORECASE)
    hrefs2 = re.findall(r'href=([^\s>"\']{10,120})', s, re.IGNORECASE)
    print("  title:", repr(title.group(1).strip()[:70]) if title else None)
    print("  company:", repr(company.group(1).strip()[:50]) if company else None)
    print("  location:", repr(location.group(1).strip()[:40]) if location else None)
    print(f"  hrefs (quoted) count={len(hrefs)} sample={[q+h+q for q,h in hrefs[:5]]}")
    print(f"  hrefs (unquoted) count={len(hrefs2)} sample={hrefs2[:5]}")
    # jobs/view özel ara
    jv = re.findall(r'/jobs/view/(\d+)', s)
    print(f"  /jobs/view/jobId count={len(jv)} sample={jv[:5]}")

print()
print("== Doğrudan href pattern test ==")
svc_url_rel = r'href="(?P<value>/jobs/view/[^"]+)"'
svc_url_abs = r'href="(?P<value>https?://[^"]*/jobs/view/[^"]+)"'
# 3. alternatif: tr.linkedin.com alt domain
svc_url_alt = r'href="(?P<value>https?://[^"]*linkedin\.com/jobs/view/[^"]+)"'
# 4. tek tırnak ile href
svc_url_sq = r"href='(?P<value>/jobs/view/[^']+)'"

good_segs = [s for s in segs if re.search(r'base-search-card__title', s)]
print(f"Good (title içeren) segment sayısı: {len(good_segs)}")

for idx, seg in enumerate(good_segs[:3]):
    seg = seg[:6000]
    m_abs = re.search(svc_url_abs, seg, re.IGNORECASE)
    m_rel = re.search(svc_url_rel, seg, re.IGNORECASE)
    m_alt = re.search(svc_url_alt, seg, re.IGNORECASE)
    m_sq = re.search(svc_url_sq, seg, re.IGNORECASE)
    print(f"\nGood seg#{idx+1}:")
    print("  m_abs  =", repr(m_abs.group('value')[:60]) if m_abs else None)
    print("  m_rel  =", repr(m_rel.group('value')[:60]) if m_rel else None)
    print("  m_alt  =", repr(m_alt.group('value')[:60]) if m_alt else None)
    print("  m_sq   =", repr(m_sq.group('value')[:60]) if m_sq else None)
    # href değerleri içinden jobs/view içerenleri filtrele
    for q in ['"', "'", ""]:
        if q:
            pat = f'href={q}([^{q}]{{15,200}}){q}'
        else:
            pat = r'href=([^\s>"\']{15,200})'
        for m in re.finditer(pat, seg, re.IGNORECASE):
            val = m.group(1)
            if "/jobs/view" in val:
                print(f"  MATCH ({'quoted '+q if q else 'unquoted'}) href=" + repr(val[:80]))
                break
        else:
            continue
        break
