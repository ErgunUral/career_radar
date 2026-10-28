#!/usr/bin/env python3
"""F10 DEBUG: LI HTML'de job ID hangi data attribute'te?"""
import re
import sys
from pathlib import Path

HTML = Path("/tmp/_li_search.html").read_text(errors="replace")

# 1) Başlıkların olduğu konumda etrafındaki data attr'leri incele
title_pat = re.compile(r'class="[^"]*base-search-card__title[^"]*"[^>]*>[\s\S]{1,120}?</\w+>', re.IGNORECASE)
t_matches = list(title_pat.finditer(HTML))
for i, tm in enumerate(t_matches[:3]):
    pos = tm.start()
    ctx = HTML[max(0, pos-3000):tm.end()+3000]
    print(f"\n=== Title #{i+1} context (6000 chars around) ===")
    # Tüm id/data-id/entity-urn/job-id/urn:li patternları
    data_matches = []
    for m in re.finditer(r'(data-[\w-]+)="([^"]{5,80})"', ctx, re.IGNORECASE):
        if any(kw in m.group(1).lower() or kw in m.group(2).lower() for kw in ["job", "urn", "id", "entity", "post"]):
            data_matches.append((m.group(1), m.group(2)))
    print(f"  data-* (job/id/urn içeren): {len(data_matches)}")
    for k, v in data_matches:
        print(f"    {k} = {v[:80]!r}")
    # Urn pattern
    urns = re.findall(r'urn:li:[a-zA-Z]+:(\d{6,})', ctx)
    print(f"  urn:li:xxx:XXXXXX job ID sayısı: {len(urns)} → örnekler: {urns[:5]}")
    # href patternları (daha kapsamlı)
    hrefs = re.findall(r'href="([^"]{15,150})"', ctx)
    # base-card class'ları içinde linkler
    a_links = re.findall(r'<a([^>]{10,400})>', ctx, re.IGNORECASE)
    jobids = re.findall(r'(?<!\w)(\d{8,12})(?!\w)', ctx)
    print(f"  8-12 digit olası job ID sayısı: {len(jobids)} → örnek: {list(dict.fromkeys(jobids))[:5]}")
    print(f"  <a> tag sample: {[s.strip()[:120] for s in a_links[:3]]}")

# 2) Tüm dosyada job ID'li arama
all_urn_job_ids = re.findall(r'urn:li:jobPosting:(\d{6,})', HTML, re.IGNORECASE)
all_job_attr = re.findall(r'data-job-id="(\d{6,})"', HTML, re.IGNORECASE)
all_entity = re.findall(r'data-entity-urn="urn:li:jobPosting:(\d{6,})"', HTML, re.IGNORECASE)
all_jobid_numeric = re.findall(r'"(?:jobPostingId|jobId|job_id|jobID)"\s*:\s*"(\d{6,})"', HTML)
print("\n\n=== Tüm dosya global job ID count ===")
print(f"  urn:li:jobPosting:XXXXXX         = {len(all_urn_job_ids)}  ör: {all_urn_job_ids[:3]}")
print(f"  data-job-id=XXXX                 = {len(all_job_attr)}  ör: {all_job_attr[:3]}")
print(f"  data-entity-urn=urn:li:job:XXXX  = {len(all_entity)}  ör: {all_entity[:3]}")
print(f"  JSON: \"jobId\": \"XXXX\"           = {len(all_jobid_numeric)}  ör: {all_jobid_numeric[:3]}")

# 3) Base card'ların 1000 chars içinde job_id var mı
split_pat = re.compile(r'<\w[^>]*\sclass="[^"]*base-card[^"]*"[^>]*>')
segs = split_pat.split(HTML)
good = [s for s in segs[1:] if re.search(r'base-search-card__title', s)]
print(f"\n=== Good segment başına ID ara ===")
for i, seg in enumerate(good[:3]):
    seg_full = split_pat.split(HTML)[segs.index(seg)-1:segs.index(seg)+2]
    big_ctx = "".join(seg_full)
    ids = re.findall(r'urn:li:jobPosting:(\d{6,})', big_ctx, re.IGNORECASE)
    ids += re.findall(r'"jobId"\s*:\s*"?(\d{6,})"?', big_ctx)
    print(f"  seg#{i+1}: {len(ids)} ID bulundu → {ids[:3]}")
    title_match = re.search(r'base-search-card__title[^>]*>([\s\S]{1,80}?)</', big_ctx, re.IGNORECASE)
    title_val = title_match.group(1).strip()[:50] if title_match else '???'
    print(f"           title: {repr(title_val)}")
