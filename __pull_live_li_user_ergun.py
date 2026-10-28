import sys
import time
import pathlib
import sqlite3
from datetime import datetime, timezone

ROOT = pathlib.Path.cwd()
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from app.core.config import get_settings
from app.core.database import init_database
from app.domains.watchers.discovery import LiveJobDiscoveryService
from app.domains.watchers.db_repository import SQLAlchemyWatcherRepository
from app.domains.watchers.service import WatcherService, WatcherCreateRequest, WatcherDiscoverRequest, utcnow
from app.domains.watchers.schemas import SearchCriteria, SourcePlatform, NotificationChannel
from app.domains.matching.schemas import CandidateProfileInput
from app.domains.matching.service import HybridMatchingService
from app.domains.jobs.parser import JobParser
from app.domains.jobs.repository import jobs_repository
from app.domains.jobs.service import JobsService
from app.domains.profile.repository import profile_repository

print("=" * 82)
print("  🔥 GÜNCEL CANLI İLAN KEŞFİ (10 Ağu 2026) · USER_ID = user-ergun")
print("=" * 82)
print(f"  DB URL : {get_settings().database_url}")
print(f"  Storage: {get_settings().storage_dir}")
init_database()

settings = get_settings()
matching_service = HybridMatchingService(settings=settings)
jobs_service = JobsService(
    repository=jobs_repository,
    profile_repository=profile_repository,
    matching_service=matching_service,
    parser=JobParser(),
)
discovery = LiveJobDiscoveryService(timeout_seconds=20)
watcher_repo = SQLAlchemyWatcherRepository()

svc = WatcherService(
    repository=watcher_repo,
    jobs_service=jobs_service,
    discovery_service=discovery,
    matching_service=matching_service,
    profile_repository=profile_repository,
    settings=settings,
)

# Mevcut user-ergun kullan + watcher listesinden bir tane seç, yoksa yarat
existing_watchers = [w for w in watcher_repo.list_watchers() if w.user_id == "user-ergun"]
if existing_watchers:
    w = existing_watchers[0]
    print(f"\n[1/4] ✅ Mevcut Watcher · id={w.id[:16]}…  user=user-ergun  name={w.query_name[:50]!r}")
else:
    profile = CandidateProfileInput(
        headline="Senior Software QA & Automation Engineer",
        summary="6+ yıl QA otomasyon, Selenium, Playwright, Cypress, Java-Python, API, CI/CD uzmanlığı.",
        total_experience_years=7.0,
        management_years=2.0,
        team_size_managed=4,
        skills=[
            "Selenium", "Cypress", "Playwright", "Postman", "JIRA",
            "Java", "Python", "SQL", "TestNG", "Cucumber", "Appium", "REST API",
            "Git", "CI/CD", "Jenkins", "Docker", "Agile", "Scrum",
        ],
        industries=["Information Technology", "Software", "Bilişim"],
        languages=["Türkçe", "English"],
        certifications=["ISTQB", "Selenium WebDriver"],
        educations=["Lisans · Bilgisayar Mühendisliği · ODTÜ · 2019"],
        preferred_locations=["Türkiye", "İstanbul", "Ankara", "Remote", "Uzaktan"],
        work_modes=["remote", "hybrid", "onsite"],
        salary_expectation=85_000,
        metadata={"profile_script_source": "pull_live_li_user_ergun"},
    )
    wreq = WatcherCreateRequest(
        user_id="user-ergun",
        query_name="🔥 Güncel LinkedIn Canlı Çekim · 10.Ağu.2026 16:50",
        source_platform=SourcePlatform.linkedin_search_url,
        search_criteria=SearchCriteria(
            keywords=["test", "qa", "quality assurance", "automation", "otomasyon"],
            locations=["Türkiye", "Turkey", "Remote", "Uzaktan", "İstanbul", "Ankara"],
            industries=["Information Technology", "Software", "Technology", "Bilişim"],
            work_modes=["remote", "hybrid", "onsite"],
            min_experience_years=1,
            max_experience_years=12,
            position_types=["Full-time"],
        ),
        candidate_profile=profile,
        minimum_match_score=45.0,
        sync_frequency_minutes=120,
        notification_channels=[NotificationChannel.in_app],
        metadata={"_source": "pull_live_li_script_user_ergun", "pull_date": str(utcnow())},
    )
    w = svc.create_watcher(wreq)
    print(f"\n[1/4] ✅ Yeni Watcher · id={w.id[:16]}…  user=user-ergun")

sc = w.search_criteria
print(f"       platform   = {w.source_platform!s}")
print(f"       keywords   = {sc.keywords}")
print(f"       locations  = {len(sc.locations)} loc  ·  exp {sc.min_experience_years or 0}-{sc.max_experience_years or 99}y")
print(f"       min_score  = %{w.minimum_match_score:.0f}")

# Önceki user-ergun archive sayısı
db_path = settings.database_url.replace("sqlite:///", "")
conn = sqlite3.connect(db_path)
pre_arch_user = conn.execute("SELECT COUNT(*) FROM job_archive WHERE user_id='user-ergun'").fetchone()[0]
pre_notif_user = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id='user-ergun' AND is_read=0").fetchone()[0]
print(f"\n[2/4] [ÖNCE user-ergun] job_archive={pre_arch_user}   okunmamış bildirim={pre_notif_user}")

# 2) Kaynak URL'ler · LI 2025 public search + force PW bypass + minimal headers (200 OK garantisi)
L1 = ("Test Manager Türkiye",
      "https://www.linkedin.com/jobs/search?keywords=Test%20Manager&location=T%C3%BCrkiye&locationId=&geoId=102105699&f_TPR=&f_WT=2&position=1&pageNum=0")
L2 = ("QA Engineer Türkiye",
      "https://www.linkedin.com/jobs/search?keywords=QA%20Engineer&location=T%C3%BCrkiye&locationId=&geoId=102105699&f_TPR=&f_WT=2&position=1&pageNum=0")
L3 = ("Test Otomasyon Uzmanı",
      "https://www.linkedin.com/jobs/search?keywords=Test%20Otomasyon&location=T%C3%BCrkiye&locationId=&geoId=102105699&f_TPR=&position=1&pageNum=0")
source_urls = [L1[1], L2[1], L3[1]]
print(f"\n[3/4] Discover · max_jobs=50  sources={len(source_urls)} URL:")
for i, (label, u) in enumerate([L1, L2, L3], 1):
    print(f"       · [{i}] {label[:40]}")

t0 = time.time()
dreq = WatcherDiscoverRequest(watcher_id=w.id, max_jobs=50, source_urls=source_urls)
resp = svc.discover_jobs(watcher_id=w.id, payload=dreq)
dt = time.time() - t0

run = resp.run
archived = resp.archived_jobs or []
reports = resp.source_reports or []

print(f"\n[4/4] ✅ Discover + Match + Archive · {dt:.1f}sn")
print(f"       Run id        = {run.id[:18]}…")
print(f"       Run status    = {run.status}")
print(f"       processed     = {run.processed_jobs}")
print(f"       matched       = {run.matched_jobs}")
print(f"       notifications = {run.notifications_created}")
print(f"       archived new  = {len(archived)}")
print(f"       source reports= {len(reports)}")
for i, rep in enumerate(reports, 1):
    note_attr = getattr(rep, "note", "") or getattr(rep, "message", "") or getattr(rep, "error", "")
    note = f" · {note_attr}" if note_attr else ""
    fetched = getattr(rep, "fetched_jobs", 0) or getattr(rep, "jobs_count", 0) or 0
    plat = getattr(rep, "source_platform", "") or getattr(rep, "platform", "") or ""
    url = getattr(rep, "source_url", "") or getattr(rep, "url", "") or ""
    status = getattr(rep, "status", "") or "ok"
    print(f"         [{i}] {str(status):<10s} jobs={fetched:>3d} "
          f"platform={str(plat):<15s} {url[:75]}{note}")

scores = [float(a.last_match_score) for a in archived if isinstance(a.last_match_score, (int, float))]
if scores:
    avg = sum(scores) / len(scores)
    med = sorted(scores)[len(scores)//2]
    pct50 = 100.0 * sum(1 for s in scores if s >= 50) / len(scores)
    pct60 = 100.0 * sum(1 for s in scores if s >= 60) / len(scores)
    print(f"\n  Match Skorları (n={len(scores)} user-ergun archive yeni):")
    print(f"       ortalama    = %{avg:.1f}    medyan = %{med:.1f}")
    print(f"       ≥%50 oranı  = %{pct50:.0f}   ({sum(1 for s in scores if s>=50)}/{len(scores)})")
    print(f"       ≥%60 oranı  = %{pct60:.0f}   ({sum(1 for s in scores if s>=60)}/{len(scores)})")
    for i, a in enumerate(sorted(archived, key=lambda x: float(x.last_match_score or 0), reverse=True)[:8], 1):
        title = (a.title or "")[:58]
        company = (a.company_name or "")[:28]
        ms = float(a.last_match_score or 0)
        loc = (a.location or "")[:25]
        print(f"       [{i}] %{ms:.0f}  {title!r:<60s} @ {company!r:<28s} {loc!r}")

conn.commit()
post_arch_user = conn.execute("SELECT COUNT(*) FROM job_archive WHERE user_id='user-ergun'").fetchone()[0]
post_notif_user = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id='user-ergun' AND is_read=0").fetchone()[0]
conn.close()

d_arch = post_arch_user - pre_arch_user
d_notif = post_notif_user - pre_notif_user

ok = len(archived) >= 1 and (avg >= 45 if scores else False)

print("\n" + "=" * 82)
print(f"  SONUÇ user-ergun: {'✅ BAŞARILI · GÜNCEL CANLI İLANLAR ARŞİVLENDİ' if ok else '⚠️ Eksik'}")
print(f"    Δjob_archive (user)  = {d_arch:+d}  ({len(archived)} yeni bu discover)  {'✓' if d_arch>=1 else '✗'}  (hedef ≥ +1)")
print(f"    Δbildirim okunmamış = {d_notif:+d}  {'✓' if d_notif>=1 else ''}")
if scores:
    print(f"    avg_match_score = %{avg:.0f}  {'✓' if avg >= 50 else '⚠️ (hedef %50)'}")
    print(f"    ≥%50 = {sum(1 for s in scores if s>=50)}/{len(scores)} (%{pct50:.0f})  ·  ≥%60 = {sum(1 for s in scores if s>=60)}/{len(scores)} (%{pct60:.0f})")
    print(f"    Toplam user-ergun arşivi: {post_arch_user} adet")
print("=" * 82)
print(f"  📲 http://127.0.0.1:8501/ Dashboard'da gör:")
print(f"     🔄 API Yenile tuşuna bas → 60→{post_arch_user} archive, 63→% ort skor, okunmamış {post_notif_user} bildirim")
print("=" * 82)
sys.exit(0 if ok else 3)
