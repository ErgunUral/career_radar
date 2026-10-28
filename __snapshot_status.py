import sys
import sqlite3
import pathlib
import datetime
import httpx
import os

sys.path.insert(0, "apps/api")
from app.core.config import get_settings

s = get_settings()
db = pathlib.Path(s.database_url.replace("sqlite:///", "")).resolve()
ts = datetime.datetime.fromtimestamp(db.stat().st_mtime)
print(f"[Storage] DB={db}")
print(f"          exists={db.exists()}  size={db.stat().st_size/1024:.0f} KB  last_modified={ts.strftime('%d.%m.%Y %H:%M:%S')}")

c = sqlite3.connect(db)

def cnt(t):
    return c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

print(
    f"[Tables] watchers={cnt('watchers')}   runs={cnt('watcher_runs')}   "
    f"archive={cnt('job_archive')}   notif={cnt('notifications')}   "
    f"jobs={cnt('jobs')}   oplog={cnt('operation_logs')}"
)

print("\n[Son 5 Watcher Run]:")
last_run = c.execute(
    "SELECT id, watcher_id, status, started_at, finished_at, processed_jobs, matched_jobs, notifications_created "
    "FROM watcher_runs ORDER BY started_at DESC LIMIT 5"
).fetchall()
for r in last_run:
    print(f"  · id={r[0][:18]}… watcher={r[1][:18]}… status={r[2]!s:<10s} "
          f"started={str(r[3])[:19]}  finished={str(r[4])[:19]}  "
          f"proc={r[5]}  match={r[6]}  notif={r[7]}")

print("\n[Son 10 Operation Log]:")
last_log = c.execute(
    "SELECT timestamp, level, source, substr(message,1,100) "
    "FROM operation_logs ORDER BY timestamp DESC LIMIT 10"
).fetchall()
for ts2, lvl, src, msg in last_log:
    print(f"  · [{str(ts2)[:19]}] {lvl:<5s} {src:<12s} {msg}")

print("\n[Archive Platform + Son Görülme]:")
for p, n, mn, mx, av in c.execute(
    "SELECT source_platform, COUNT(*), MIN(last_seen_at), MAX(last_seen_at), ROUND(AVG(last_match_score),2) "
    "FROM job_archive GROUP BY 1 ORDER BY 2 DESC"
).fetchall():
    print(f"  {str(p):<22s} n={n:>3d}  ort=%{av}  first={str(mn)[:16]}  last={str(mx)[:16]}")

n, avg, med, p50, p60 = c.execute(
    "SELECT COUNT(*), ROUND(AVG(last_match_score),2), "
    "(SELECT last_match_score FROM job_archive ORDER BY last_match_score LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM job_archive)), "
    "ROUND(100.0*SUM(CASE WHEN last_match_score>=50 THEN 1 ELSE 0 END)/COUNT(*),0), "
    "ROUND(100.0*SUM(CASE WHEN last_match_score>=60 THEN 1 ELSE 0 END)/COUNT(*),0) "
    "FROM job_archive"
).fetchone()
print(f"  TOTAL archive n={n}   avg=%{avg}   med=%{med}   >=%50=%{p50}   >=%60=%{p60}")

print("\n[HTTP Canlılık]:")
os.environ["no_proxy"] = "127.0.0.1,localhost"
cli = httpx.Client(timeout=6, follow_redirects=True)
for name, url in [("API health", "http://127.0.0.1:8000/health"),
                   ("API watchers", "http://127.0.0.1:8000/api/watchers?user_id=user-ergun"),
                   ("UI Streamlit", "http://127.0.0.1:8501/")]:
    try:
        r = cli.get(url)
        ct = (r.headers.get("content-type") or "")[:40]
        print(f"  {name!s:<14s} {url} → HTTP {r.status_code}  ({len(r.content):>6d} bytes)  Content-Type: {ct}")
    except Exception as e:
        print(f"  {name!s:<14s} {url} → ❌ HATA: {type(e).__name__} {e}")
cli.close()

# Son user-ergun archive eklenme tarihi (last_seen_at MAX)
u_row = c.execute(
    "SELECT COUNT(*), MAX(last_seen_at), ROUND(AVG(last_match_score),2) FROM job_archive WHERE user_id='user-ergun'"
).fetchone()
print(f"\n[user-ergun archive]: n={u_row[0]}   last_seen_max={u_row[1]}   ort_skor=%{u_row[2]}")
u_noread = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id='user-ergun' AND is_read=0").fetchone()[0]
print(f"[user-ergun bildirim]: okunmamış={u_noread}")
c.close()
