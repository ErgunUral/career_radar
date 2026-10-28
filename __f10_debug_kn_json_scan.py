#!/usr/bin/env python3
"""F10 DEBUG v2: KN SPA HTML → Script tag JSON bul (window.__data, JSON-LD, __NEXT_DATA__, etc.)"""
import json
import re
import sys
from pathlib import Path

HTML_FILE = Path("/tmp/_kn_search.html")


def extract_jsons(html: str):
    out: list[tuple[str, int]] = []

    # 1) JSON-LD: <script type="application/ld+json">...</script>
    for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', html, re.IGNORECASE):
        try:
            data = json.loads(m.group(1).strip())
            out.append(("JSON-LD", len(json.dumps(data))))
            with open("/tmp/_kn_jsonld.json", "w") as fp:
                json.dump(data, fp, indent=2, ensure_ascii=False)
            if isinstance(data, dict):
                print(f"  JSON-LD keys: {list(data.keys())[:15]}")
            elif isinstance(data, list):
                print(f"  JSON-LD list len={len(data)}")
                if data:
                    print(f"    ilk item type = {type(data[0]).__name__}")
        except Exception as e:
            print(f"  JSON-LD parse err: {e}")

    # 2) <script> window.* = { veya window.__... =
    patterns = [
        ("window.__data", r"window\.__data\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>"),
        ("window.__INITIAL_STATE", r"window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>"),
        ("window.APP_DATA", r"window\.APP_DATA\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>"),
        ("window.PAGE_DATA", r"window\.PAGE_DATA\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>"),
        ("var data=", r"var\s+data\s*=\s*(\{[\s\S]{100,}?\})\s*;"),
        ("JSON.parse('<script", r"JSON\.parse\(['\"](\{[^{}]{50,}?\})['\"]\)"),
    ]
    for name, pat in patterns:
        m = re.search(pat, html, re.MULTILINE)
        if not m:
            print(f"  {name:<25} NOT FOUND")
            continue
        raw = m.group(1).strip()
        try:
            d = json.loads(raw)
            print(f"  {name:<25} OK keys(top10)={list(d.keys())[:10] if isinstance(d, dict) else type(d).__name__}")
            with open(f"/tmp/_kn_{name.replace(' ','_').replace('.','_').replace('__','_')}.json", "w") as fp:
                json.dump(d, fp, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  {name:<25} found {len(raw)} chars but parse err: {e}")

    # 3) __NEXT_DATA__
    next_m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>([\s\S]*?)</script>', html, re.IGNORECASE)
    if next_m:
        try:
            d = json.loads(next_m.group(1).strip())
            print(f"  __NEXT_DATA__             OK  size={len(json.dumps(d))//1024}KB")
            with open("/tmp/_kn_next_data.json", "w") as fp:
                json.dump(d, fp, indent=2, ensure_ascii=False)
            pages = d.get("props", {}).get("pageProps") if isinstance(d, dict) else None
            if pages:
                print(f"    pageProps keys={list(pages.keys())[:12]}")
                for k, v in list(pages.items())[:8]:
                    if isinstance(v, (list, dict)):
                        n = len(v) if isinstance(v, list) else len(list(v.keys()))
                        print(f"      · {k:<40} (len {n})  {type(v).__name__}")
        except Exception as e:
            print(f"  __NEXT_DATA__ parse err: {e}")

    # 4) Bütün script taglarındaki JSON bulalım: herhangi bir scriptte uzun JSON ({...})
    all_scripts = re.findall(r"<script[^>]*>([\s\S]{500,}?)</script>", html, re.IGNORECASE)
    print(f"\nToplam 500+ chars script sayısı: {len(all_scripts)}")
    for i, s in enumerate(all_scripts[:4]):
        # object başlangıcı bul: JSON object array parse dene
        # ilk object match
        for match in re.finditer(r"(\{[\s\S]{2000,}?\})\s*(?:;|$|\n)", s):
            raw = match.group(1)
            try:
                d = json.loads(raw)
                fp = f"/tmp/_kn_script_{i}_big.json"
                with open(fp, "w") as f:
                    json.dump(d, f, indent=2, ensure_ascii=False)
                n_keys = len(d) if isinstance(d, dict) else len(d) if isinstance(d, list) else 0
                print(f"  script#{i} embedded JSON OK → {fp} (size {len(raw)//1024}KB)")
                print(f"    top keys={list(d.keys())[:15] if isinstance(d, dict) else f'list len={len(d)}'}")
                break
            except Exception:
                pass


def find_ilan_references(html: str):
    """JSON içinde keywords arama."""
    terms = ["job_title", "jobTitle", "title", "companyName", "company_name", "ilan", "advert", "jobPosting"]
    print("\nReferanslar (JSON dosyalarında anahtar):")
    for f in sorted(Path("/tmp").glob("_kn_*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        founds: dict[str, int] = {}
        def walk(o, depth=0):
            if depth > 8:
                return
            if isinstance(o, dict):
                for k, v in o.items():
                    kl = k.lower()
                    for t in terms:
                        if t.lower() in kl:
                            founds[t] = founds.get(t, 0) + 1
                    walk(v, depth+1)
            elif isinstance(o, list):
                for x in o[:100]:
                    walk(x, depth+1)
        walk(d)
        if founds:
            print(f"  {f.name:<35} → job anahtarları: {founds}")
            # Derinlemesine job list bul
            if isinstance(d, dict):
                def find_arrays(o, depth=0, path=""):
                    if depth > 10:
                        return
                    if isinstance(o, dict):
                        for k, v in o.items():
                            if isinstance(v, list) and len(v) >= 3:
                                sample = v[0] if v else None
                                t = type(sample).__name__
                                print(f"      ARRAY  {path}.{k:<35} len={len(v):<4}  ilk={t}")
                                # içinde title varsa
                                if isinstance(sample, dict):
                                    keys = list(sample.keys())
                                    if any(k2 in ("title","companyName","positionName","jobTitle","advertTitle") for k2 in keys):
                                        print(f"         → İLANLAR BURADA! keys: {keys[:15]}")
                                        with open(f"/tmp/_kn_found_jobs.json", "w") as fp:
                                            json.dump(v[:5], fp, indent=2, ensure_ascii=False)
                                        print(f"         → ilk 5 ilan /tmp/_kn_found_jobs.json kaydedildi")
                            find_arrays(v, depth+1, f"{path}.{k}")
                    elif isinstance(o, list):
                        for idx, x in enumerate(o[:20]):
                            find_arrays(x, depth+1, f"{path}[{idx}]")
                find_arrays(d)
        else:
            print(f"  {f.name:<35} → job anahtarı BULUNAMADI")


def main() -> int:
    print("=" * 70)
    print("F10 DEBUG v2: KN SPA → embedded JSON scan")
    print("=" * 70)
    html = HTML_FILE.read_text(errors="replace")
    print(f"HTML size: {len(html)} chars ({len(html.encode())//1024} KB)")
    print()
    extract_jsons(html)
    print()
    find_ilan_references(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
