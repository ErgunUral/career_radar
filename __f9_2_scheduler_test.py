#!/usr/bin/env python3
"""F9_2: APScheduler CANLI Test (scheduler/status + run/watcher via HTTP API)."""
import json
import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api/v1"
DB_PATH = Path(__file__).parent / "apps" / "api" / "careerradar.db"


def http(method, path, body=None, timeout=600):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        client = httpx.Client(timeout=timeout)
        if method == "GET":
            r = client.get(API + path, headers=headers, params=body if isinstance(body, dict) else None)
        else:
            r = client.request(method, API + path, headers=headers, json=body)
        return r.status_code, r.json() if r.text else None
    except Exception as e:
        return 500, {"error": type(e).__name__, "msg": str(e)[:200]}


def count_rows(table, where_sql="", args=()) -> int:
    import sqlite3
    if not DB_PATH.exists():
        return -1
    with sqlite3.connect(str(DB_PATH)) as cnx:
        return cnx.execute(f"SELECT COUNT(*) FROM {table} {where_sql}", args).fetchone()[0]


def main() -> int:
    print("=" * 70)
    print("F9_2: APScheduler CANLI Test (HTTP API)")
    print("=" * 70)

    print("\n[1/6] GET /watchers — mevcut watcherlar:")
    st, watchers = http("GET", "/watchers")
    print(f"  HTTP {st} · count={len(watchers) if isinstance(watchers, list) else '?'}")
    watcher_id = None
    if isinstance(watchers, list) and watchers:
        for w in watchers:
            wid = w.get("id")
            name = w.get("query_name")
            active = w.get("is_active")
            print(f"    - id={wid}  active={active}  name={name}")
            if active and not watcher_id:
                watcher_id = wid
    else:
        print(f"  DEBUG: {json.dumps(watchers, ensure_ascii=False)[:400]}")

    if not watcher_id:
        print("  ⚠️  Aktif watcher YOK — test sonlandırılıyor.")
        return 1

    wr_before = count_rows("watcher_runs")
    wr_before_w = count_rows("watcher_runs", "WHERE watcher_id=?", (watcher_id,))
    logs_before = count_rows("operation_logs")
    print(f"\n[2/6] Önce DB sayıları:")
    print(f"  watcher_runs (toplam)        : {wr_before}")
    print(f"  watcher_runs (this watcher)  : {wr_before_w}")
    print(f"  operation_logs               : {logs_before}")

    print("\n[3/6] GET /scheduler/status:")
    st, status = http("GET", "/scheduler/status")
    print(f"  HTTP {st}")
    for k, v in (status.items() if isinstance(status, dict) else {}):
        print(f"    {k:<25}: {v}")
    sched_running = (
        isinstance(status, dict) and status.get("running") is True
    ) or (isinstance(status, dict) and status.get("is_running") is True)
    print(f"  ✔ Running = {sched_running}")

    print(f"\n[4/6] POST /scheduler/run/{watcher_id} — tek watcher çalıştır (timeout=600sn BG):")
    t0 = time.time()
    # Note: Will do actual discover + match so it may take >30s, but we set long timeout
    try:
        st, result = http("POST", f"/scheduler/run/{watcher_id}", timeout=480)
        elapsed = time.time() - t0
        print(f"  HTTP {st} · Süre: {elapsed:.1f}sn")
        if isinstance(result, dict) and result.get("summary"):
            s = result["summary"]
            print(f"  summary:")
            for k in [
                "watchers_dispatched",
                "watchers_failed",
                "processed_jobs_total",
                "matched_jobs_total",
                "notifications_created_total",
                "duration_seconds",
            ]:
                if k in s:
                    print(f"    {k:<25}: {s[k]}")
            per = s.get("per_watcher") or []
            if per:
                pw = per[0]
                print(f"  per_watcher[0]: status={pw.get('status')}  processed={pw.get('processed_jobs')}  matched={pw.get('matched_jobs')}  err={pw.get('error')}")
                reports = pw.get("source_reports") or []
                for r in reports:
                    status_val = r.get("status") if isinstance(r, dict) else "?"
                    jobs = r.get("fetched_jobs", 0) if isinstance(r, dict) else 0
                    url = (r.get("source_url", "") if isinstance(r, dict) else "")[:80]
                    print(f"    src_report [{status_val}] jobs={jobs}  {url}")
        elif isinstance(result, dict):
            txt = json.dumps(result, ensure_ascii=False)[:600]
            print(f"  result: {txt}")
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"  ❌ HTTP Client error: {type(exc).__name__}: {str(exc)[:200]}  (Süre: {elapsed:.1f}sn)")

    print(f"\n[5/6] Sonra DB sayıları (sonucu karşılaştır):")
    time.sleep(1.2)
    wr_after = count_rows("watcher_runs")
    wr_after_w = count_rows("watcher_runs", "WHERE watcher_id=?", (watcher_id,))
    logs_after = count_rows("operation_logs")
    print(f"  watcher_runs (toplam)        : {wr_after}      (Δ = {wr_after - wr_before})")
    print(f"  watcher_runs (this watcher)  : {wr_after_w}      (Δ = {wr_after_w - wr_before_w})")
    print(f"  operation_logs               : {logs_after}      (Δ = {logs_after - logs_before})")

    print("\n[6/6] Son 3 watcher_runs (started_at DESC):")
    import sqlite3
    with sqlite3.connect(str(DB_PATH)) as cnx:
        cnx.row_factory = sqlite3.Row
        rows = cnx.execute(
            "SELECT id, watcher_id, status, started_at, finished_at, processed_jobs, matched_jobs, notifications_created, error_message FROM watcher_runs ORDER BY started_at DESC LIMIT 3"
        ).fetchall()
    for r in rows:
        cols = [r[k] for k in r.keys()]
        pretty = {k: (str(v)[:25] if v is not None else None) for k, v in zip(r.keys(), cols)}
        print(f"  id={pretty['id'][-12:]}  wid={pretty['watcher_id'][-12:]}  status={pretty['status']:<9}  proc={pretty['processed_jobs']}  matched={pretty['matched_jobs']}  notif={pretty['notifications_created']}  err={pretty['error_message']}")

    print("\n" + "=" * 70)
    delta_run = wr_after_w - wr_before_w
    delta_log = logs_after - logs_before
    ok = delta_run >= 1 or (logs_after >= 1 and sched_running)
    print(f"  {'✅' if ok else '⚠️'} Faz 9_2 Scheduler test: Δ watcher_runs={delta_run}, Δ operation_logs={delta_log}, scheduler_running={sched_running}")
    print("=" * 70)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
