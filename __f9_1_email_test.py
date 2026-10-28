#!/usr/bin/env python3
"""F9_1: EmailSenderService SMTP env kontrol + Test email."""
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

from app.domains.watchers.service import EmailSenderService, ArchiveRecord  # noqa: E402


def main() -> int:
    print("=" * 70)
    print("F9_1: EmailSenderService SMTP kontrol + Test mail")
    print("=" * 70)

    print()
    print("ENV kontrol (SMTP_*):")
    for k in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"]:
        v = os.environ.get(k, "")
        if v and k == "SMTP_PASS":
            mask = "***" + v[-3:] if len(v) >= 4 else "***"
        else:
            mask = v
        print(f"  {k:<12} = {mask!r:<25}  SET={bool(v.strip())}")

    svc = EmailSenderService()
    print()
    print(f"is_configured (host+port+user+pass) = {svc.is_configured}")
    print(f"  host     = {svc.host!r}")
    print(f"  port     = {svc.port}")
    print(f"  user     = {svc.user!r}")
    print(f"  sender   = {svc.sender!r}")

    now = datetime.now(timezone.utc)
    test_archive = ArchiveRecord(
        user_id="user-ergun",
        watcher_id="watcher-f9-dry-run",
        job_id="job-f9-test-001",
        title="Senior QA Automation Engineer (Playwright)",
        company_name="TechFlow Bilişim A.Ş.",
        location="İstanbul / Remote (Hibrit)",
        source_platform="kariyer_net",
        source_url="https://www.kariyer.net/is-ilani/senior-qa-automation-engineer/fake-1234567",
        first_seen_at=now,
        last_seen_at=now,
        notification_sent=False,
        notifications_sent=0,
        last_match_score=91.5,
        last_recommendation="Hızlıca başvuru yapın. 15 yıl deneyim QA Lideri seviyesi çok uygun.",
    )

    test_to = os.environ.get("SMTP_TEST_TO", "").strip()
    if not test_to:
        test_to = svc.user if svc.user else ""
    print()
    if svc.is_configured:
        target = test_to or svc.user
        print(f"✅ SMTP AYARLI. Gerçek test mail gönderiliyor → {target}")
        t0 = time.time()
        ok = svc.send_match_notification(target, test_archive, total_score=test_archive.last_match_score)
        dt = time.time() - t0
        print(f"  Sonuç: {'GÖNDERİLDİ ✅' if ok else 'GÖNDERİLEMEDİ ❌'}  Süre: {dt:.2f}s")
        if not ok:
            print("  Not: EmailSenderService exception atmaz, sessizce False döner")
            print("  Debug önerisi:")
            print("    1) Ping: SMTP host/port doğru mu? (telnet SMTP_HOST SMTP_PORT)")
            print("    2) Gmail ise: 2FA açık → 'App Password' kullan (normal şifre DEĞİL)")
            print("    3) Güvenlik duvarı: 465/587 portları açık mı?")
    else:
        print("ℹ️ SMTP ENV ayarlanmamış (normal/güvenlik). DRY-RUN body:")
        print()
        print("  TO  : erg***@******  (SMTP_USER)")
        print(
            f"  SUB : [CareerRadar] %{test_archive.last_match_score:.1f} Eşleşme: "
            f"{test_archive.title} @ {test_archive.company_name}"
        )
        print("  BODY:")
        body = f"""Merhaba,

Yeni bir high-match ilan bulundu:

  Başlık      : {test_archive.title}
  Şirket      : {test_archive.company_name or 'Belirtilmemiş'}
  Konum       : {test_archive.location or 'Belirtilmemiş'}
  Platform    : {test_archive.source_platform or '-'}
  Skor        : %{test_archive.last_match_score:.2f}
  İlan Linki  : {test_archive.source_url or '-'}
  Öneri       : {test_archive.last_recommendation or '-'}

Dashboard'dan detayları görüntüleyebilirsiniz:
  http://localhost:8501

İyi çalışmalar,
CareerRadar AI · Kişisel İş Radar Paneli
"""
        for i, ln in enumerate(body.splitlines()[:14], 1):
            mark = "│" if i > 3 else "├"
            print(f"  {mark} {ln}")
        print()
        print("SMTP aktif etmek için (örnek Gmail):")
        print("  export SMTP_HOST=smtp.gmail.com")
        print("  export SMTP_PORT=465")
        print("  export SMTP_USER=adiniz@firma.com")
        print("  export SMTP_PASS='xxxx xxxx xxxx xxxx'  # Google App Password (16 harf, arada boşluk)")
        print("  export SMTP_FROM='CareerRadar AI <adiniz@firma.com>'")

    print()
    print("=" * 70)
    print(f"SONUÇ: SMTP configured = {svc.is_configured}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
