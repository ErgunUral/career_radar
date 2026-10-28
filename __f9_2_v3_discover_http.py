#!/usr/bin/env python3
"""F9_2 v3: APScheduler status + DISCOVER (HTTP POST) kullanarak Watcher canlı test.

Alternatif: /scheduler/run/{id} endpoint metadata URL cache sorunu.
Burada /watchers/{id}/discover + source_urls=... (explicit body) kullanıyoruz
ki scheduler katmanındaki URL fetch ile aynı discover_jobs() çağrılır.
"""
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api/v1"
WID_FILE = Path("/tmp/_f9_wid.txt")
DB_PATH = Path(__file__).parent / "apps" / "api" / "careerradar.db"


def count_rows(table, where="", args=()):
    with sqlite3.connect(str(DB_PATH)) as cnx:
        cur = cnx.execute(f"SELECT COUNT(*) FROM {table} {where}", args)
        return cur.fetchone()[0]


def main() -> int:
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    print("=" * 70)
    print("F9_2: APScheduler RUNNING + Watcher Discover HTTP Test")
    print("=" * 70)

    wid = WID_FILE.read_text().strip() if WID_FILE.exists() else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    client = httpx.Client(timeout=480)

    # Step 1: scheduler status (BackgroundScheduler check)
    print("\n[1/5] GET /scheduler/status:")
    r = client.get(API + "/scheduler/status", timeout=60)
    sched_running = False
    if r.status_code == 200:
        d = r.json()
        sched_running = bool(d.get("running"))
        interval = d.get("interval_minutes")
        print(f"  HTTP {r.status_code}")
        print(f"    enabled={d.get('enabled')}  running={d.get('running')}  interval={interval}dk  max_jobs={d.get('max_jobs_per_run')}")
        print(f"    last_run_at = {d.get('last_run_at')}")
        jobs = d.get("jobs") or []
        print(f"    jobs       : {len(jobs)} adet")
        for j in jobs[:2]:
            print(f"      · {j.get('id')}: {j.get('trigger')}  next={j.get('next_run_time')[:25] if j.get('next_run_time') else '-'}")
    else:
        print(f"  HATA: HTTP {r.status_code}  {r.text[:300]}")

    # Step 2: Create if watcher not found via list
    print("\n[2/5] GET /watchers list:")
    r = client.get(API + "/watchers", timeout=60)
    items = r.json() if r.status_code == 200 else []
    print(f"  HTTP {r.status_code}  count={len(items)}")
    if items:
        for w in items[:3]:
            print(f"    · id={w['id'][-12:]}  active={w['is_active']}  name={w['query_name'][:40]}")
        if not wid:
            wid = items[0]["id"]
            print(f"  → kullanılan watcher id: {wid}")

    if not wid:
        print("❌ Watcher ID yok, çıkılıyor.")
        return 1

    # Step 3: Önce DB sayıları (watcher_runs, operation_logs)
    print("\n[3/5] DB sayıları (ÖNCE):")
    wr_before = count_rows("watcher_runs")
    wr_before_w = count_rows("watcher_runs", "WHERE watcher_id=?", (wid,))
    logs_before = count_rows("operation_logs")
    print(f"  watcher_runs   : {wr_before} (this w: {wr_before_w})")
    print(f"  operation_logs : {logs_before}")

    # Step 4: POST /watchers/{wid}/discover  (source_urls explicit in payload)
    source_urls = [
        "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689",
        "https://www.kariyer.net/is-ilanlari?kw=qa+manager&cs=35689",
        "https://www.yenibiri.com/is-ilanlari?q=test+yoneticisi",
    ]
    body = {
        "source_urls": source_urls,
        "triggered_by": "manual_single",
        "max_jobs": 10,
    }
    print(f"\n[4/5] POST /watchers/{wid}/discover:")
    print(f"  URL sayısı = {len(source_urls)}  max_jobs={body['max_jobs']}")
    t0 = time.time()
    r = client.post(API + f"/watchers/{wid}/discover", json=body, headers=headers, timeout=480)
    dt = time.time() - t0
    print(f"  HTTP {r.status_code} · Süre: {dt:.1f}s")
    if r.status_code >= 400:
        print(f"  detail: {r.text[:800]}")
    else:
        d = r.json()
        run = d.get("run") or {}
        reports = (d.get("source_reports") or (run.get("metadata") or {}).get("source_reports")) or []
        print(f"  run_id           : {(run.get('id') or '?')[-12:]}")
        print(f"  status           : {run.get('status')}")
        print(f"  processed_jobs   : {run.get('processed_jobs')}")
        print(f"  matched_jobs     : {run.get('matched_jobs')}")
        print(f"  notifications    : {run.get('notifications_created')}")
        if reports:
            print(f"  source_reports ({len(reports)} adet):")
            for rep in reports[:6]:
                sp = rep.get("source_platform") or "-"
                if hasattr(sp, "value"):
                    sp = sp.value
                note = rep.get("verification_note") or ""
                print(f"    · [{rep.get('status'):<9}] {sp:<15} jobs={rep.get('fetched_jobs'):<3} url='{rep.get('source_url','')[:55]}'  {note[:90]}")

    # Step 5: Sonra DB sayıları + son watcher_runs satırları
    print("\n[5/5] DB sayıları (SONRA):")
    time.sleep(1.5)
    wr_after = count_rows("watcher_runs")
    wr_after_w = count_rows("watcher_runs", "WHERE watcher_id=?", (wid,))
    logs_after = count_rows("operation_logs")
    print(f"  watcher_runs   : {wr_after}   Δ = {wr_after - wr_before}  (this w: {wr_after_w} Δ {wr_after_w - wr_before_w})")
    print(f"  operation_logs : {logs_after}   Δ = {logs_after - logs_before}")

    print("\nSon 3 watcher_runs (started_at DESC):")
    with sqlite3.connect(str(DB_PATH)) as cnx:
        cnx.row_factory = sqlite3.Row
        rows = cnx.execute(
            "SELECT id, watcher_id, status, started_at, finished_at, processed_jobs, matched_jobs, notifications_created, error_message FROM watcher_runs ORDER BY started_at DESC LIMIT 3"
        ).fetchall()
    for r in rows:
        cols = {k: (str(r[k])[:30] if r[k] is not None else "-") for k in r.keys()}
        print(f"  id={cols['id'][-12:]}  status={cols['status']:<10}  proc={cols['processed_jobs']:<3}  matched={cols['matched_jobs']:<3}  notif={cols['notifications_created']:<3}  start={cols['started_at'][:19]}  err={cols['error_message'][:40]}")

    delta_run = wr_after_w - wr_before_w
    delta_log = logs_after - logs_before
    ok = (delta_run >= 1) and sched_running
    print("\n" + "=" * 70)
    print(f"  {'✅' if ok else '⚠️'} Faz 9_2 Scheduler test:")
    print(f"     scheduler_running         = {sched_running}")
    print(f"     Δ watcher_runs (watcher)  = {delta_run}  (beklenen ≥ 1)")
    print(f"     Δ operation_logs          = {delta_log}  (beklenen ≥ 3)")
    print("=" * 70)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
