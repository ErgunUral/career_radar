#!/usr/bin/env python3
"""F10 DEBUG: /jobs/view href konumunu bul — title'dan 5000 char geriye bak."""
import re
import sys
from pathlib import Path

HTML = Path("/tmp/_li_search.html").read_text(errors="replace")

# 1) Tüm /jobs/view/ URL sayısı
print("== Tüm URL sayımıza bakalım:")
all_jv = re.findall(r'href="([^"]*/jobs/view/\d+[^"]*)"', HTML, re.IGNORECASE)
print(f"  /jobs/view/XXXX href sayısı (dolu): {len(all_jv)}")
for u in all_jv[:6]:
    print("   ·", u[:90])

# 2) Her title'dan geriye 8000 chars ara
print("\n== Her title 8000 char öncesinde URL var mı?")
title_pat = re.compile(r'class="[^"]*base-search-card__title[^"]*"[^>]*>([\s\S]{1,120}?)</\w+>', re.IGNORECASE)
found_pairs = 0
missing = 0
t_matches = list(title_pat.finditer(HTML))
for i, tm in enumerate(t_matches[:5]):
    title_clean = re.sub(r'<[^>]+>', ' ', tm.group(1)).strip()[:55]
    pos = tm.start()
    lookback = HTML[max(0, pos-8000):pos]
    lookahead = HTML[pos:pos+12000]
    # lookback + lookahead combined
    context = lookback + lookahead
    m_rel = re.findall(r'href="([^"]*/jobs/view/\d+[^"]*)"', context, re.IGNORECASE)
    m_abs = re.findall(r'href="(https?://[^"]*linkedin\.com/jobs/view/\d+[^"]*)"', context, re.IGNORECASE)
    all_found = list(dict.fromkeys(m_rel + m_abs))
    if all_found:
        found_pairs += 1
        print(f"  [{i}] {title_clean!r}")
        for url in all_found[:3]:
            print(f"     → {url[:95]}")
    else:
        missing += 1
        print(f"  [{i}] {title_clean!r}  -> HİÇ URL YOK (arama: start={pos}, len_context={len(context)}")

print(f"\n  {found_pairs} paired / {missing} missing")
