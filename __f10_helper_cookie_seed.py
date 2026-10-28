#!/usr/bin/env python3
"""F10 Helper: httpx ile KN/YeniBiri ilk ziyaret + Set-Cookie headerları → storage_state JSON oluştur.

Ayrıca her source URL için HTTP status + body bytes + anti-bot challenge kontrolü yap.
"""
import json
import re
import sys
import time
from pathlib import Path

import httpx

STATE_PATH = Path(__file__).parent / "apps" / "api" / "app" / "storage" / "playwright_state.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

WARMUP_URLS = [
    ("KN anasayfa", "https://www.kariyer.net/", "kariyer.net"),
    ("KN search", "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689", "kariyer.net"),
    ("YB anasayfa", "https://www.yenibiri.com/", "yenibiri.com"),
    ("YB search", "https://www.yenibiri.com/is-ilanlari?q=test+yoneticisi", "yenibiri.com"),
]

ANTI_BOT_PATTERNS = re.compile(
    r"(cloudflare|just a moment|doğrulama|rate limit|robot kontrol|challenge|captcha|hız sınırı)",
    re.IGNORECASE,
)


def cookie_from_setcookie(header: str, domain_suffix: str) -> list[dict]:
    """Set-Cookie headerından Playwright cookie dict dizisi çıkar."""
    out: list[dict] = []
    for pair in re.split(r",\s*(?=[^;,\s]+=)", header):
        try:
            parts = [p.strip() for p in pair.split(";")]
            if not parts:
                continue
            name_eq = parts[0].split("=", 1)
            if len(name_eq) != 2:
                continue
            name, val = name_eq[0].strip(), name_eq[1].strip()
            if not name:
                continue
            flags: dict[str, str] = {}
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    flags[k.strip().lower()] = v.strip()
                else:
                    flags[p.strip().lower()] = "1"
            domain = flags.get("domain") or f".{domain_suffix}"
            if not domain.startswith("."):
                domain = f".{domain}"
            out.append({
                "name": name,
                "value": val,
                "domain": domain,
                "path": flags.get("path") or "/",
                "expires": -1,
                "httpOnly": "httponly" in flags,
                "secure": "secure" in flags,
                "sameSite": "Lax",
            })
        except Exception:
            continue
    return out


def main() -> int:
    print("=" * 70)
    print("F10_HELPER: httpx first-visit cookies → storage_state")
    print("=" * 70)

    print("\n[1/3] KN + YB ilk ziyaret (httpx):")
    all_cookies: list[dict] = []
    transport = httpx.HTTPTransport(retries=1)
    try:
        client = httpx.Client(transport=transport, timeout=30.0, follow_redirects=True,
                              headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})
    except Exception as e:
        print(f"client init HATA: {e}")
        return 2

    for idx, (name, url, domain_suffix) in enumerate(WARMUP_URLS, 1):
        t0 = time.time()
        try:
            r = client.get(url)
            dt = time.time() - t0
            bytes_len = len(r.content or b"")
            title_m = re.search(r"<title[^>]*>(.*?)</title>", r.text or "", re.IGNORECASE | re.DOTALL)
            title = (title_m.group(1).strip()[:70]) if title_m else "(no title)"
            is_anti_bot = bool(ANTI_BOT_PATTERNS.search(r.text or ""))
            cards_count = len(re.findall(r"(ilanKarti|job-item|job-card|ilankarti|\bilanlar\b)", r.text or "", flags=re.IGNORECASE))
            set_cookies_all = r.headers.get_list("set-cookie")
            for sc in set_cookies_all:
                all_cookies.extend(cookie_from_setcookie(sc, domain_suffix))
            print(f"  [{idx}] {name}")
            print(f"      status={r.status_code}  body={bytes_len//1024}KB  time={dt:.1f}s  title={title[:65]}")
            print(f"      job-cards-visible={cards_count}  set-cookie={len(set_cookies_all)}  anti-bot={is_anti_bot}")
        except Exception as e:
            print(f"  [{idx}] {name} HATA: {type(e).__name__}: {e!s}")

    # Playwright storage_state format
    try:
        client.close()
    except Exception:
        pass

    # Benzersizleştir
    seen: set[tuple[str, str, str]] = set()
    uniq: list[dict] = []
    for c in all_cookies:
        key = (c.get("domain") or "", c.get("path") or "/", c.get("name") or "")
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)

    state = {"cookies": uniq, "origins": []}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = STATE_PATH.stat().st_size if STATE_PATH.exists() else 0
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    after = STATE_PATH.stat().st_size
    print("\n[2/3] storage_state kaydedildi:")
    print(f"  before={before} bytes   after={after} bytes   Δ = {after - before} bytes")
    print(f"  cookies  = {len(uniq)} adet")

    domains: dict[str, int] = {}
    for c in uniq:
        domains[c.get("domain") or "?"] = domains.get(c.get("domain") or "?", 0) + 1
    print(f"  domains (top {min(len(domains), 5)}):")
    for d, n in list(sorted(domains.items(), key=lambda kv: -kv[1]))[:5]:
        print(f"    · {d:<35} {n}")

    # Son olarak storage_state JSON içeriği doğrula
    check = json.loads(STATE_PATH.read_text())
    print(f"\n[3/3] Doğrulama: cookies={len(check.get('cookies') or [])}  origins={len(check.get('origins') or [])}")
    ok = len(uniq) >= 3
    print("\n" + "=" * 70)
    print(f"SONUÇ: {'✅ DOLDURULDU' if ok else '⚠️ Kısmi'}  (min 3 cookie hedefliyoruz)")
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
