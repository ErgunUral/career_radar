"""URL çıkarmak için: job_archive.metadata JSON'dan source_url → GERÇEK ilan URL'i. Eğer bozuksa job_id'den re-construct."""
import html
import json
import re
import sqlite3
import sys
import pathlib
import typing as t
import urllib.parse

_LINKEDIN_JOB_RE = re.compile(r"(?:view|jobs)/(\d{8,14})")
_LI_URL_PREFIX = "https://www.linkedin.com/jobs/view/"
_SAFE_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)
# URL içinde ASLA bulunmamalı (attribute injection / XSS) — varsa URL block
_UNSAFE_URL_CHARS_RE = re.compile(r"[\"`<>\\\x00-\x20]")  # çift tırnak, backtick, <, >, \, space + control chars


def sanitize_url(url: t.Optional[str]) -> str:
    """XSS/open redirect koruması:
    - URL yalnızca http/https ile başlamalı
    - İçinde ", <, >, boşluk gibi HTML attribute enjekte edecek karakterler VARSA # döndür
    - Değilse URL güvenli döndür.
    """
    if not url:
        return "#"
    s = str(url).strip()
    if not s:
        return "#"
    s = s.replace("\r", "").replace("\n", "").replace("\t", "")
    if not _SAFE_SCHEME_RE.match(s):
        return "#"
    if _UNSAFE_URL_CHARS_RE.search(s):
        return "#"
    return s


def safe_html_anchor(
    url: t.Optional[str],
    label: str,
    *,
    extra_css_class: str = "job-link",
    target_blank: bool = True,
) -> str:
    """Güvenli bir HTML <a> etiketi üretir: URL scheme whitelist + label HTML escape + URL attribute escape."""
    clean_url = sanitize_url(url)
    # URL içindeki " ve < > kaçışlarını URL attribute içi için html.escape (quote=True yapılır
    safe_url_attr = html.escape(clean_url, quote=True)
    safe_label = html.escape(str(label or ""), quote=False)
    target = ' target="_blank" rel="noopener noreferrer"' if target_blank else ""
    cls = f' class="{html.escape(extra_css_class, quote=True)}"' if extra_css_class else ""
    return f"<a{cls}{target} href=\"{safe_url_attr}\">{safe_label}</a>"

def extract_url_from_row(
    *,
    source_platform: str,
    job_id: str,
    metadata: t.Any,
    title: str = "",
    company_name: str = "",
) -> str:
    """Satırdan URL çıkar. Öncelik sırası: metadata.source_url > apply_url > reconstruct."""
    # 1) metadata parse
    md = None
    if isinstance(metadata, str) and metadata:
        try:
            md = json.loads(metadata)
        except Exception:
            md = None
    elif isinstance(metadata, dict):
        md = metadata

    # 2) metadata'nın doğrudan URL içeren key'lerini tara
    if isinstance(md, dict):
        for k in (
            "source_url",
            "apply_url",
            "applyLink",
            "url",
            "link",
            "job_url",
            "job_link",
            "external_apply_url",
            "raw_url",
        ):
            v = md.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v.strip()

    # 3) metadata içinde herhangi bir yerde http ile başlayan str ara (derin ilk 1 seviye)
    if isinstance(md, dict):
        for v in md.values():
            if isinstance(v, str) and v.startswith("http") and ("job" in v or "ilan" in v or "kariyer" in v or "linkedin" in v):
                return v.strip()

    plat = (source_platform or "").lower()

    # 4) LinkedIn
    if "linkedin" in plat:
        # metadata'da 8-14 haneli job ID var mı?
        if isinstance(md, dict):
            flat = " ".join(str(v) for v in md.values() if isinstance(v, str))
            m = _LINKEDIN_JOB_RE.search(flat)
            if m:
                return f"{_LI_URL_PREFIX}{m.group(1)}"
        # job_id içinden
        if job_id:
            m = re.search(r"(\d{8,14})", str(job_id))
            if m:
                return f"{_LI_URL_PREFIX}{m.group(1)}"
        # boş: arama URL'i fallback
        kw = "+".join(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", (title or "")[:60])) or "Test+QA"
        loc = "+".join(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", (company_name or "")[:40])) or ""
        return f"https://www.linkedin.com/jobs/search?keywords={kw}&location=T%C3%BCrkiye{f'&company={loc}' if loc else ''}"

    # 5) KariyerNET (8 Ağu kayıtları, metadata JSON varsa yukarıda çıkar)
    if "kariyer" in plat or "kariyernet" in plat:
        if isinstance(md, dict):
            flat = " ".join(str(v) for v in md.values() if isinstance(v, str))
            for pat in (r"https://www\.kariyer\.net/is-ilan[a-zıöüşçğ]*[^\s\"'<>)]+",):
                m = re.search(pat, flat)
                if m:
                    return m.group(0)
        if isinstance(job_id, str) and len(job_id) > 4:
            # job_id bir kariyernet slug içeriyorsa
            slug = re.sub(r"[^A-Za-z0-9\-]+", "-", f"{title or ''}-{company_name or ''}").strip("-").lower()
            jid = re.sub(r"[^a-z0-9]", "", str(job_id).lower())
            return f"https://www.kariyer.net/is-ilanlari?kw={slug[:80] or jid or 'test+yoneticisi'}"

    # 6) Diğer: LinkedIn search fallback
    return f"https://www.linkedin.com/jobs/search?keywords=Test+QA+Automation&location=T%C3%BCrkiye"


def add_url_column_to_rows(rows: t.List[dict], conn: t.Optional[sqlite3.Connection] = None, db_path: t.Optional[pathlib.Path] = None) -> t.List[dict]:
    """Her satıra `apply_url` ekle. Gerekirse DB'den metadata çeker."""
    needs_fetch = any("metadata" not in r for r in rows[:3])
    if needs_fetch and (conn or db_path):
        close_later = False
        if conn is None:
            conn = sqlite3.connect(db_path)
            close_later = True
        cur = conn.cursor()
        ids = [int(r["id"]) for r in rows if isinstance(r.get("id"), int)]
        placeholders = ",".join("?" * len(ids)) if ids else "0"
        cur.execute(
            f"SELECT id, metadata FROM job_archive WHERE id IN ({placeholders})",
            ids,
        )
        meta_map = {rowid: md for rowid, md in cur.fetchall()}
        if close_later:
            conn.close()
        for r in rows:
            if isinstance(r.get("id"), int) and r["id"] in meta_map:
                r["metadata"] = meta_map[r["id"]]

    for r in rows:
        r["apply_url"] = sanitize_url(
            extract_url_from_row(
                source_platform=r.get("source_platform") or "",
                job_id=r.get("job_id") or "",
                metadata=r.get("metadata"),
                title=r.get("title") or "",
                company_name=r.get("company_name") or "",
            )
        )
    return rows


if __name__ == "__main__":
    # Hızlı sanity
    sys.path.insert(0, "apps/api")
    from app.core.config import get_settings
    db = pathlib.Path(get_settings().database_url.replace("sqlite:///", "")).resolve()
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT id, source_platform, job_id, title, company_name, metadata FROM job_archive ORDER BY id DESC LIMIT 15")
    rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    add_url_column_to_rows(rows)
    c200=c302=c404=cxxx=0
    import httpx
    cli = httpx.Client(timeout=7, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.6"
    })
    for r in rows:
        url = r["apply_url"]
        try:
            resp = cli.get(url)
            code = resp.status_code
        except Exception as e:
            code = -1
        if code == 200: c200 += 1
        elif code in (302, 301, 307, 308): c302 += 1
        elif code == 404: c404 += 1
        else: cxxx += 1
        print(f"  [{code:>3d}] plat={r['source_platform']!s:<20s} id={r['id']:<3d}  job_id={r['job_id'][:20]!r}  url={url[:110]}")
    cli.close()
    conn.close()
    print(f"\n  Toplam 15 sample: 200={c200}  3xx={c302}  404={c404}  other={cxxx}")
