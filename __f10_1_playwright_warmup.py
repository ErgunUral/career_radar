#!/usr/bin/env python3
"""F10_1: Headless Playwright ile session cookie warm-up.

Manuel login gerekmeden önce ilk ziyaret cookie'leri + localStorage set edilir.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

URLS_TO_VISIT = [
    ("KariyerNET anasayfa", "https://www.kariyer.net/"),
    ("KariyerNET test yoneticisi", "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689"),
    ("YeniBiri anasayfa", "https://www.yenibiri.com/"),
]

STATE_PATH = Path(__file__).parent / "apps" / "api" / "app" / "storage" / "playwright_state.json"


def main() -> int:
    print("=" * 70)
    print("F10_1: Playwright cookie warm-up (storage_state doldurma)")
    print("=" * 70)
    print(f"Hedef path: {STATE_PATH}")
    before = STATE_PATH.read_text() if STATE_PATH.exists() else ""
    print(f"Önce boyut: {len(before.encode('utf-8'))} bytes")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(f"❌ Playwright kurulu değil: {exc}")
        return 2

    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    t0 = __import__("time").time()
    with sync_playwright() as pw:
        print("\nLaunch Chromium (headless)...")
        browser = pw.chromium.launch(headless=True, args=[
            "--no-sandbox", "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ])
        ctx_kwargs = {
            "user_agent": ua,
            "locale": "tr-TR",
            "viewport": {"width": 1440, "height": 900},
            "color_scheme": "light",
        }
        if STATE_PATH.exists() and STATE_PATH.stat().st_size > 40:
            ctx_kwargs["storage_state"] = str(STATE_PATH)
        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()

        for name, url in URLS_TO_VISIT:
            print(f"\n→ {name}: {url}")
            try:
                resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                print(f"   status  : {resp.status if resp else '?'}")
                title = page.title() or ""
                print(f"   title   : {title[:80]}")
                page.wait_for_timeout(1800)
                cookies_count = len(ctx.cookies())
                print(f"   cookies : {cookies_count} adet")
            except Exception as e:
                print(f"   ⚠️ HATA: {type(e).__name__}: {e!s}")

        # Kaydet
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state = ctx.storage_state(path=str(STATE_PATH))
        cookies_n = len(state.get("cookies", []))
        origins_n = len(state.get("origins", []) if isinstance(state.get("origins"), list) else list(state.get("origins", {}).keys()))
        print("\n" + "=" * 70)
        print(f"Kaydedildi: {STATE_PATH}")
        print(f"  cookies  = {cookies_n}")
        print(f"  origins  = {origins_n}")
        after_bytes = STATE_PATH.stat().st_size
        print(f"  bytes    = {after_bytes}  (Önce: {len(before.encode('utf-8'))} → Δ {after_bytes - len(before.encode('utf-8'))})")

        try:
            page.close()
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

    dt = __import__("time").time() - t0
    print(f"  süre     : {dt:.1f}s")

    # Son kontrol
    state2 = json.loads(STATE_PATH.read_text())
    cookies_list = state2.get("cookies") or []
    print()
    print("Cookie özeti (domain bazlı):")
    domains: dict[str, int] = {}
    for c in cookies_list:
        d = c.get("domain") or "?"
        domains[d] = domains.get(d, 0) + 1
    for d, n in list(domains.items())[:8]:
        print(f"  · {d:<40} {n} cookie")

    ok = len(cookies_list) >= 1
    print()
    print("=" * 70)
    print(f"SONUÇ: {'✅ DOLDURULDU' if ok else '⚠️ Yetersiz cookie (≥1 lazım)'}  (total {len(cookies_list)} cookie)")
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
