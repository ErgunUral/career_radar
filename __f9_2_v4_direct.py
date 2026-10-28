#!/usr/bin/env python3
"""F9_2 v4: Direct Service Test - APScheduler status + WatcherService.discover_jobs().

HTTP'ye güvenmeden, doğrudan Python katmanından:
1. Scheduler BG status kontrolü (HTTP GET ile yapıyoruz zaten)
2. DB sayımları (ÖNCE)
3. WatcherService().discover_jobs() = 1 tek URL, max_jobs=3
4. DB sayımları (SONRA) - Δ beklediğimiz ≥1
"""
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))
os.chdir(Path(__file__).parent / "apps" / "api")

from app.core.config import get_settings  # noqa: E402
from app.domains.watchers.discovery import LiveJobDiscoveryService  # noqa: E402
from app.domains.watchers.repository import repository as _inmem_repo  # noqa: E402
from app.domains.watchers.db_repository import db_repository  # noqa: E402
from app.domains.watchers.schemas import (  # noqa: E402
    WatcherDiscoverRequest,
)
from app.domains.watchers.service import WatcherService  # noqa: E402
from app.domains.jobs.repository import jobs_repository  # noqa: E402
from app.domains.profile.repository import profile_repository  # noqa: E402
from app.domains.matching.service import HybridMatchingService  # noqa: E402
from app.domains.jobs.service import JobsService  # noqa: E402
from app.domains.jobs.parser import JobParser  # noqa: E402
import httpx  # noqa: E402


API = "http://127.0.0.1:8000/api/v1"
DB_PATH = Path("careerradar.db")
WID_FILE = Path("/tmp/_f9_wid.txt")


def count_rows(table, where="", args=()):
    with sqlite3.connect(str(DB_PATH)) as cnx:
        return cnx.execute(f"SELECT COUNT(*) FROM {table} {where}", args).fetchone()[0]


def main() -> int:
    print("=" * 70)
    print("F9_2: APScheduler BG OK + Direct Service Discover (1 URL, max 3 job)")
    print("=" * 70)

    # 1) Scheduler status (HTTP GET, hızlı)
    sched_running = False
    print("\n[1/5] GET /scheduler/status:")
    try:
        r = httpx.get(API + "/scheduler/status", timeout=10.0)
        if r.status_code == 200:
            d = r.json()
            sched_running = bool(d.get("running"))
            jobs = d.get("jobs") or []
            print(f"  HTTP 200   running={sched_running}   interval={d.get('interval_minutes')}dk   jobs={len(jobs)}")
            for j in jobs[:2]:
                print(f"    · {j.get('name')}: trigger={j.get('trigger')}  next_run={str(j.get('next_run_time'))[:25]}")
    except Exception as e:
        print(f"  ⚠️ HTTP Hatası: {type(e).__name__}: {e}")

    # 2) Watcher ve DB sayıları (ÖNCE)
    wid = WID_FILE.read_text().strip() if WID_FILE.exists() else None
    if not wid:
        print("❌ Watcher ID yok. Çıkılıyor.")
        return 1
    print(f"\n[2/5] Watcher ID: {wid}")
    wr_before = count_rows("watcher_runs")
    wr_before_w = count_rows("watcher_runs", "WHERE watcher_id=?", (wid,))
    logs_before = count_rows("operation_logs")
    print(f"  [ÖNCE] watcher_runs  : {wr_before}  (this w: {wr_before_w})")
    print(f"  [ÖNCE] operation_logs: {logs_before}")

    # 3) Doğrudan Service katmanından discover_jobs çağır
    settings = get_settings()
    matching = HybridMatchingService(settings=settings)
    jobs_svc = JobsService(
        repository=jobs_repository,
        profile_repository=profile_repository,
        matching_service=matching,
        parser=JobParser(),
    )
    service = WatcherService(
        repository=db_repository,
        matching_service=matching,
        settings=settings,
        profile_repository=profile_repository,
        jobs_service=jobs_svc,
        discovery_service=LiveJobDiscoveryService(
            timeout_seconds=15.0,
            debug_mode=False,
        ),
    )

    url_list = [
        "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689",
    ]
    req = WatcherDiscoverRequest(
        source_urls=url_list, triggered_by="manual_single", max_jobs=3
    )
    print(f"\n[3/5] WatcherService.discover_jobs() — {len(url_list)} URL, max_jobs={req.max_jobs}")
    t0 = time.time()
    try:
        response = service.discover_jobs(wid, req)
        dt = time.time() - t0
    except Exception as exc:
        dt = time.time() - t0
        print(f"  ❌ Exception: {type(exc).__name__}: {exc}")
        print(f"     geçen süre: {dt:.1f}s")
        # log_event yine de yazıldı mı bakalım
        time.sleep(1.0)
        logs_after_mid = count_rows("operation_logs")
        print(f"     Δ logs: {logs_after_mid - logs_before}")
        response = None

    if response is not None:
        run = response.run
        reports = response.source_reports
        print(f"  ✅ Süre: {dt:.2f}s")
        print(f"  run_id        : {run.id[-12:]}")
        print(f"  status        : {run.status}")
        print(f"  processed_jobs: {run.processed_jobs}")
        print(f"  matched_jobs  : {run.matched_jobs}")
        print(f"  notifications : {run.notifications_created}")
        if run.error_message:
            print(f"  error_message : {run.error_message[:200]}")
        if reports:
            print(f"  source_reports ({len(reports)} adet):")
            for rep in reports:
                sp = rep.source_platform.value if rep.source_platform and hasattr(rep.source_platform, "value") else str(rep.source_platform)
                note = rep.verification_note or ""
                print(f"    · [{rep.status:<9}] {sp:<17} jobs={rep.fetched_jobs:<3} search={rep.search_performed}   {note[:110]}")

    # 4) DB sayıları (SONRA)
    print(f"\n[4/5] DB sayıları (SONRA):")
    time.sleep(1.5)
    wr_after = count_rows("watcher_runs")
    wr_after_w = count_rows("watcher_runs", "WHERE watcher_id=?", (wid,))
    logs_after = count_rows("operation_logs")
    d_run = wr_after_w - wr_before_w
    d_log = logs_after - logs_before
    print(f"  [SONRA] watcher_runs  : {wr_after}   Δ = {wr_after - wr_before}  (this w: {wr_after_w} Δ {d_run})")
    print(f"  [SONRA] operation_logs: {logs_after}   Δ = {d_log}")

    # 5) Son watcher_runs satırı
    print("\n[5/5] Son watcher_runs kaydı:")
    with sqlite3.connect(str(DB_PATH)) as cnx:
        cnx.row_factory = sqlite3.Row
        rows = cnx.execute(
            "SELECT id, watcher_id, status, started_at, finished_at, processed_jobs, matched_jobs, notifications_created, error_message FROM watcher_runs ORDER BY started_at DESC LIMIT 2"
        ).fetchall()
    for r in rows:
        err = (r["error_message"] or "")[:60]
        start = str(r["started_at"] or "-")[:19]
        print(f"  id={r['id'][-12:]}  status={str(r['status']):<10}  proc={r['processed_jobs']}  matched={r['matched_jobs']}  notif={r['notifications_created']}  {start}  err={err!r}")

    print("\nSon 3 operation_logs (timestamp DESC):")
    with sqlite3.connect(str(DB_PATH)) as cnx:
        cnx.row_factory = sqlite3.Row
        rows = cnx.execute(
            "SELECT timestamp, level, source, message FROM operation_logs WHERE watcher_id=? ORDER BY timestamp DESC LIMIT 3",
            (wid,),
        ).fetchall()
    for r in rows:
        msg = r["message"][:80]
        ts = str(r["timestamp"] or "-")[:19]
        print(f"  [{ts}] {r['level']:<6} {r['source']:<13} {msg}")

    # Sonuç
    ok = sched_running and d_run >= 1
    print("\n" + "=" * 70)
    print(f"  {'✅' if ok else '⚠️'} Faz 9_2 SONUÇ:")
    print(f"    APScheduler running  = {sched_running}  (beklenen True)")
    print(f"    Δ watcher_runs       = {d_run}  (beklenen ≥ 1)")
    print(f"    Δ operation_logs     = {d_log}  (beklenen ≥ 3)")
    print("=" * 70)

    # Kaynak temizle
    try:
        service.discovery_service.close_playwright_pool()
    except Exception:
        pass

    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
