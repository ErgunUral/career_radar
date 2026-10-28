"""
Faz 8_2c: GERÇEK Discover Retry v3 (doğrudan Python)
===================================================
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.database import init_database, engine  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.domains.jobs.service import JobsService  # noqa: E402
from app.domains.jobs.parser import JobParser  # noqa: E402
from app.domains.jobs.repository import jobs_repository  # noqa: E402
from app.domains.profile.repository import profile_repository  # noqa: E402
from app.domains.matching.service import HybridMatchingService  # noqa: E402
from app.domains.watchers.db_repository import db_repository  # noqa: E402
from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402
from app.domains.watchers.schemas import WatcherDiscoverRequest  # noqa: E402
from app.domains.watchers.service import WatcherService  # noqa: E402

WATCHER_ID = (
    Path("/tmp/_fw_wid.txt").read_text().strip()
    if Path("/tmp/_fw_wid.txt").exists()
    else "watcher-effd39c00314"
)
USER_ID = "user-ergun"
MAX_JOBS = 3
SOURCES = [
    "https://www.kariyer.net/is-ilanlari?k=Test+Yoneticisi",
]


def query_db(sql: str, params: tuple | None = None) -> list[dict]:
    con = sqlite3.connect(str(engine.url.database))
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql, params or ())
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def build_service() -> WatcherService:
    settings = get_settings()
    init_database()
    matching_service = HybridMatchingService(settings=settings)
    jobs_service = JobsService(
        repository=jobs_repository,
        profile_repository=profile_repository,
        matching_service=matching_service,
        parser=JobParser(),
    )
    return WatcherService(
        repository=db_repository,
        matching_service=matching_service,
        settings=settings,
        profile_repository=profile_repository,
        jobs_service=jobs_service,
        discovery_service=LiveJobDiscoveryService(),
    )


def main() -> int:
    print("=" * 70)
    print("FAZ 8_2c: WatcherService Direct Discover (HTTP YOK, v3)")
    print("=" * 70)
    print(f"  Watcher ID    : {WATCHER_ID}")
    print(f"  User          : {USER_ID}")
    print(f"  Max Jobs      : {MAX_JOBS}")
    for i, s in enumerate(SOURCES, 1):
        print(f"  URL {i}         : {s}")

    print("\n[1/4] Service build...")
    svc = build_service()

    print(f"\n[2/4] Önceki durum:")
    archives_before = query_db(
        "SELECT COUNT(*) as cnt FROM job_archive WHERE user_id = ? OR user_id IS NULL",
        (USER_ID,),
    )[0]["cnt"]
    logs_before = query_db(
        "SELECT COUNT(*) as cnt FROM operation_logs WHERE user_id = ? OR user_id IS NULL",
        (USER_ID,),
    )[0]["cnt"]
    print(f"  Önce Archive (user=ergun OR NULL): {archives_before}")
    print(f"  Önce Log     (user=ergun OR NULL): {logs_before}")

    req = WatcherDiscoverRequest(
        source_urls=SOURCES,
        max_jobs=MAX_JOBS,
        triggered_by="faz8-direct-python-v3",
    )
    print(f"\n[3/4] discover_jobs çalıştırılıyor... (Süre sınırı YOK)")
    t0 = time.time()
    try:
        result = svc.discover_jobs(watcher_id=WATCHER_ID, payload=req)
        elapsed = time.time() - t0
        print(f"  ✅ Bitti. Süre = {elapsed:.1f}s")
        print(f"  run_id           = {result.run_id}")
        print(f"  watcher_id       = {result.watcher_id}")
        print(f"  discovered_raw   = {result.discovered_jobs_count}")
        print(f"  archived         = {len(result.archived_jobs)}")
        print(f"  notifications    = {result.notifications_created_count}")
        reports = result.source_reports or []
        print(f"  kaynak raporu    = {len(reports)} adet")
        for r in reports:
            status = (
                getattr(r.status, "value", str(r.status))
                if hasattr(r.status, "value")
                else str(r.status)
            )
            url = (r.source_url or "")[:90]
            print(
                f"    - [{status}] jobs={r.fetched_jobs}  err={r.error_message or '-'}  {url}"
            )
        if result.archived_jobs:
            print(f"\n  Arşivlenen {len(result.archived_jobs)} iş:")
            for a in result.archived_jobs[:5]:
                score = getattr(a, "match_score", None) or 0
                co = getattr(a, "company_name", None) or "?"
                title = (getattr(a, "title", None) or "")[:70]
                print(f"    %{score:.0f} @{co[:25]:<25} | {title}")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ❌ HATA: {type(e).__name__}: {str(e)[:600]}")
        print(f"     Süre: {elapsed:.1f}s")
        import traceback

        traceback.print_exc()
        return 2

    print(f"\n[4/4] Son durum: SQLite doğrulama...")
    archives_after = query_db(
        "SELECT COUNT(*) as cnt FROM job_archive WHERE user_id = ? OR user_id IS NULL",
        (USER_ID,),
    )[0]["cnt"]
    logs_after = query_db(
        "SELECT COUNT(*) as cnt FROM operation_logs WHERE user_id = ? OR user_id IS NULL",
        (USER_ID,),
    )[0]["cnt"]
    print(
        f"  Sonra Archive (user=ergun OR NULL): {archives_after}  (Δ = {archives_after - archives_before})"
    )
    print(
        f"  Sonra Log     (user=ergun OR NULL): {logs_after}      (Δ = {logs_after - logs_before})"
    )

    if archives_after > 0:
        last5a = query_db(
            "SELECT id, user_id, title, company, match_score, source_platform, created_at FROM job_archive "
            "WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC LIMIT 5",
            (USER_ID,),
        )
        print("\n  Son 5 Arşiv:")
        for r in last5a:
            print(
                f"    id={r['id']} u={r['user_id'] or '-'} %{(r['match_score'] or 0):.0f} @{(r['company'] or '')[:25]} | {(r['title'] or '')[:60]}"
            )

    last5l = query_db(
        "SELECT id, user_id, level, source, message, created_at FROM operation_logs "
        "WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC LIMIT 7",
        (USER_ID,),
    )
    if last5l:
        print("\n  Son 7 Operation Log:")
        for r in last5l:
            print(
                f"    [{r['level']:<5}] {r['source']:<10} u={r['user_id'] or '-':<12} | {(r['message'] or '')[:90]}"
            )

    print("\n" + "=" * 70)
    ok = (archives_after > archives_before) and (logs_after > logs_before)
    print(
        f"  {'✅' if ok else '⚠️'} Faz 8_2c Tamamlandı. "
        f"Archive Δ={archives_after - archives_before}, Log Δ={logs_after - logs_before}"
    )
    print("=" * 70)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
