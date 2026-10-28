#!/usr/bin/env python3
"""F10_1 v2: Playwright launch args = LiveJobDiscoveryService._PW_CHROMIUM_ARGS ile aynı."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))
os.chdir(Path(__file__).parent / "apps" / "api")

from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402

URLS_TO_VISIT = [
    ("KariyerNET anasayfa", "https://www.kariyer.net/"),
    ("KariyerNET search", "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689"),
    ("YeniBiri anasayfa", "https://www.yenibiri.com/"),
    ("YeniBiri search", "https://www.yenibiri.com/is-ilanlari?q=qa+manager"),
]


def main() -> int:
    settings_storage_path = Path(os.environ.get(
        "STORAGE_OVERRIDE",
        Path(__file__).resolve().parent / "apps" / "api" / "app" / "storage" / "playwright_state.json",
    ))
    print("=" * 70)
    print("F10_1 v2: Playwright warm-up (LiveJobDiscoveryService args)")
    print("=" * 70)
    print(f"Hedef: {settings_storage_path}")
    print(f"  exists_before = {settings_storage_path.exists()}")
    before_bytes = settings_storage_path.stat().st_size if settings_storage_path.exists() else 0
    print(f"  size_before   = {before_bytes} bytes")

    svc = LiveJobDiscoveryService(
        timeout_seconds=25.0,
        debug_mode=False,
        storage_state_path=str(settings_storage_path),
        slow_mo_ms=0,
    )
    ua = svc.CHROME_UA
    lang = "tr-TR"
    headless = True

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(f"❌ playwright yok: {exc}")
        return 2

    t0 = time.time()
    ok = False
    try:
        with sync_playwright() as pw_mgr:
            print("\nLaunching Chromium (args = LiveJobDiscoveryService._PW_CHROMIUM_ARGS)...")
            bargs = {
                "headless": headless,
                "args": list(LiveJobDiscoveryService._PW_CHROMIUM_ARGS),
            }
            browser = pw_mgr.chromium.launch(**bargs)
            ctx_kwargs = dict(
                user_agent=ua,
                locale=lang[:5],
                accept_downloads=False,
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                ignore_https_errors=True,
                color_scheme="light",
                java_script_enabled=True,
            )
            if str(settings_storage_path) and os.path.isfile(str(settings_storage_path)):
                sz = os.stat(str(settings_storage_path)).st_size
                if sz > 40:
                    ctx_kwargs["storage_state"] = str(settings_storage_path)
            ctx = browser.new_context(**ctx_kwargs)
            page = ctx.new_page()

            cookies_start = len(ctx.cookies())
            print(f"  cookies öncesi = {cookies_start}")
            for idx, (name, url) in enumerate(URLS_TO_VISIT, 1):
                print(f"\n[{idx}/{len(URLS_TO_VISIT)}] → {name}:")
                print(f"    url = {url}")
                try:
                    resp = page.goto(url, timeout=40000, wait_until="domcontentloaded")
                    print(f"    status = {resp.status if resp else '?'}")
                    title = page.title() or ""
                    print(f"    title  = {title[:90]}")
                    time.sleep(2.5)
                    n_cookies = len(ctx.cookies())
                    print(f"    cookies (şu an) = {n_cookies}")
                except Exception as exc:
                    print(f"    ⚠️ HATA: {type(exc).__name__}: {exc!s}")
                sys.stdout.flush()

            # Save state
            settings_storage_path.parent.mkdir(parents=True, exist_ok=True)
            state = ctx.storage_state(path=str(settings_storage_path))
            after_bytes = settings_storage_path.stat().st_size
            cookies_n = len(state.get("cookies") or [])
            origins = state.get("origins")
            if isinstance(origins, list):
                origins_n = len(origins)
            elif isinstance(origins, dict):
                origins_n = len(origins)
            else:
                origins_n = 0
            print("\n" + "=" * 70)
            print(f"✅ Kaydedildi: {settings_storage_path}")
            print(f"  bytes (before → after): {before_bytes} → {after_bytes}   Δ = {after_bytes - before_bytes}")
            print(f"  cookies count          : {cookies_n}")
            print(f"  origins count          : {origins_n}")

            # Cookie domains özeti
            domains: dict[str, int] = {}
            for c in state.get("cookies") or []:
                d = c.get("domain") or "?"
                domains[d] = domains.get(d, 0) + 1
            print(f"\nCookie domains (top {min(len(domains), 6)}):")
            for d, n in list(sorted(domains.items(), key=lambda kv: -kv[1]))[:6]:
                print(f"  · {d:<40} {n} adet")

            ok = cookies_n >= 5

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
    finally:
        try:
            svc.close_playwright_pool()
        except Exception:
            pass

    dt = time.time() - t0
    print(f"\nToplam süre: {dt:.1f}s")
    print()
    print("=" * 70)
    mark = "✅ DOLDURULDU" if ok else "⚠️ Kısmi (gerçek login lazım)"
    print(f"SONUÇ: {mark}  (cookies = {cookies_n} / min 5)")
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
