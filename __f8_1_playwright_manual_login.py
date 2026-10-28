"""
FAZ 8_1: Playwright Manuel Login + Storage State Doldur
=======================================================
- pw_headless_override=False ile HEADED chromium açılır
- Kullanıcı 120 sn içinde kariyer.net + linkedin.com için manuel login yapar
- Sonunda playwright_state.json 36 bytes boştan 1KB+ cookies doluya çıkar
- Kullanım: python3 __f8_1_playwright_manual_login.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402

LOGIN_URLS = [
    "https://www.kariyer.net/aday/giris-yap",
    "https://www.linkedin.com/login",
]
WAIT_SECONDS = 120


def main() -> None:
    print("=" * 70)
    print("FAZ 8_1: Playwright Manuel Login + Storage State Kaydet")
    print("=" * 70)
    print(f"\nTarayıcı açılıyor... Başarılı login için {WAIT_SECONDS}sn süreniz var")
    print(f"Login URL'leri ({len(LOGIN_URLS)} adet):")
    for i, u in enumerate(LOGIN_URLS, 1):
        print(f"  {i}. {u}")
    print(f"\nStorage State hedef: {LiveJobDiscoveryService.storage_state_path}")

    svc = LiveJobDiscoveryService(
        debug_mode=True,
        pw_headless_override=False,
        slow_mo_ms=200,
    )

    try:
        svc._ensure_playwright_pool()
        if svc._pw_context is None:
            print("  ❌ HATA: _pw_context oluşturulamadı (Playwright kurulu mu?)")
            return

        pages = []
        for i, url in enumerate(LOGIN_URLS):
            if i == 0:
                page = svc._pw_context.pages[0] if svc._pw_context.pages else svc._pw_context.new_page()
            else:
                page = svc._pw_context.new_page()
            print(f"\n🚀 [{i+1}/{len(LOGIN_URLS)}] Açılıyor: {url}")
            page.goto(url, timeout=90_000)
            pages.append(page)

        print(f"\n⏳ LÜTFEN {WAIT_SECONDS}sn İÇİNDE MANUEL LOGIN YAPIN (2 site için)")
        print(f"   Süre bittiğinde otomatik storage_state kaydedilecektir.")

        start = time.time()
        while time.time() - start < WAIT_SECONDS:
            remain = int(WAIT_SECONDS - (time.time() - start))
            if remain % 15 == 0 and remain > 0:
                print(f"   ⏱️  Kalan süre: {remain}sn")
            time.sleep(1)

        print(f"\n✅ Süre bitti. Storage State kaydediliyor...")
        state_path = Path(svc.storage_state_path) if svc.storage_state_path else None
        if state_path:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            svc._pw_context.storage_state(path=str(state_path))
            size = state_path.stat().st_size
            print(f"   ✅ {state_path} boyutu: {size} bytes")
            if size < 500:
                print(f"   ⚠️  Boyut çok küçük (<500 bytes). Login başarısız olabilir.")
            else:
                print(f"   🎉 Login KAYDEDİLDİ. {size} bytes (cookies + localStorage + origins)")
        else:
            print("   ❌ storage_state_path None")

    except KeyboardInterrupt:
        print("\n⏹️  Kullanıcı tarafından iptal edildi")
    finally:
        try:
            svc._close_playwright_pool()
        except Exception:
            pass
        print("\n🏁 Tarayıcı kapatıldı. Bitti.")


if __name__ == "__main__":
    main()
