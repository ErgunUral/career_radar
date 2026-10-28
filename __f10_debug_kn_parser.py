#!/usr/bin/env python3
"""F10 DEBUG: KN search HTML kaydet + parser çalıştır, regex'leri debug et."""
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

from app.domains.jobs.parser import JobParser  # noqa: E402
from app.domains.jobs.schemas import JobSourcePlatform  # noqa: E402

URL = "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689"
HTML_FILE = Path("/tmp/_kn_search.html")


def main() -> int:
    UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    if not HTML_FILE.exists() or HTML_FILE.stat().st_size < 5000:
        print(f"httpx GET → {URL}")
        r = httpx.get(URL, timeout=30.0, follow_redirects=True,
                      headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})
        print(f"  HTTP {r.status_code} · {len(r.content)//1024} KB")
        HTML_FILE.write_bytes(r.content or b"")
    else:
        print(f"HTML önceden kaydedilmiş: {HTML_FILE} ({HTML_FILE.stat().st_size//1024} KB)")

    html = HTML_FILE.read_text(errors="replace")
    print(f"\nHTML toplam {len(html)} chars")

    # 1. Hızlı card pattern sayımı
    patterns = [
        ("ilanKarti class", r"ilanKarti"),
        ("job-item class", r"job-item"),
        ("job-card class", r"job-card"),
        ("ilanlar liste", r"ilanlar"),
        ("data-job-id attr", r"data-job-id"),
        ("href /is-ilani/", r"/is-ilani/[\w-]+"),
        ("h3 veya h5 (başlık)", r"<h[35][^>]*>"),
        ("a (link)", r"<a[^>]*href=[\"']/is-ilani/"),
    ]
    print("\nPattern sayımları:")
    for name, pat in patterns:
        m = re.findall(pat, html, flags=re.IGNORECASE)
        print(f"  {name:<25} → {len(m):>3} kez")
        if m and name == "href /is-ilani/":
            uniq = list(dict.fromkeys(m))[:5]
            for u in uniq:
                print(f"      · {u[:70]}")

    # 2. Parser'ı doğrudan çağır
    print("\n=== JobParser.parse_source_html(KariyerNET) çağrısı ===")
    parser = JobParser()
    try:
        jobs = parser.parse_source_html(
            source_url=URL,
            source_platform=JobSourcePlatform.KARIYERNET,
            html=html,
            max_jobs=20,
        )
        print(f"→ Parse edilen job sayısı: {len(jobs)}")
        for i, job in enumerate(jobs[:8], 1):
            pj = job.parsed_job if hasattr(job, "parsed_job") else None
            title = getattr(pj, "title", "") or ""
            company = getattr(pj, "company_name", "") or ""
            loc = getattr(pj, "location", "") or ""
            url = getattr(pj, "source_url", "") or ""
            print(f"  [{i:>2}] {title[:60]:<60} @{company[:25]:<25}  {loc[:20]}")
            print(f"       {url[:80]}")
    except Exception as exc:
        print(f"❌ Parser exception: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc(limit=5)
        return 2

    # 3. Eğer 0 job ise, parserdaki KN regex'lerini kontrol et
    if len(jobs) == 0:
        print("\n→ 0 job parse edildi. Parser regex'leri doğrudan test ediliyor:")
        from app.domains.jobs.parser import KariyerNetParser
        parser_kn = KariyerNetParser()
        for pat_name, pat in [
            ("re_card", getattr(parser_kn, "re_card", None)),
            ("re_title", getattr(parser_kn, "re_title", None)),
            ("re_company", getattr(parser_kn, "re_company", None)),
            ("re_location", getattr(parser_kn, "re_location", None)),
            ("re_link", getattr(parser_kn, "re_link", None)),
        ]:
            if pat is None:
                continue
            pat_str = pat.pattern if hasattr(pat, "pattern") else str(pat)
            matches = re.findall(pat_str, html, flags=re.IGNORECASE | re.DOTALL)
            print(f"  {pat_name:<15} → len={len(matches)}   regex[:60]={pat_str[:80]!r}")

    # 4. İlk 10 KB snippet (card etrafında)
    idx = html.find("ilanKarti")
    if idx > 0:
        print(f"\nİlk 'ilanKarti' çevresi (index {idx}):")
        snippet = html[max(0, idx-150):idx+400]
        print("  " + snippet.replace("\n", " ").replace("  ", " ")[:600])
    else:
        idx = html.find("job-item")
        if idx > 0:
            snippet = html[max(0, idx-150):idx+400]
            print(f"\nİlk 'job-item' çevresi (index {idx}):")
            print("  " + snippet.replace("\n", " ").replace("  ", " ")[:600])

    return 0


if __name__ == "__main__":
    sys.exit(main())
