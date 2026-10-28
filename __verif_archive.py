import sqlite3, pathlib, sys
sys.path.insert(0, 'apps/api')
from app.core.config import get_settings
db = pathlib.Path(get_settings().database_url.replace('sqlite:///','')).resolve()
print(f"DB={db}   var={db.exists()}  size={db.stat().st_size} bytes")
c = sqlite3.connect(db)
def cnt(t):
    return c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
print(f"watchers={cnt('watchers')}   runs={cnt('watcher_runs')}   archive={cnt('job_archive')}   notif={cnt('notifications')}   jobs={cnt('jobs')}   oplog={cnt('operation_logs')}")

rows = c.execute(
    "SELECT source_platform, COUNT(*), MIN(last_seen_at), MAX(last_seen_at), ROUND(AVG(last_match_score),1) FROM job_archive GROUP BY 1 ORDER BY 2 DESC"
).fetchall()
for p, n, mn, mx, av in rows:
    print(f"   platform={str(p):<20s} n={n:>3d}   ort=%{av}   aralık={mn[:16]}  → {mx[:16]}")

n, avg, med, p50, p60 = c.execute(
    "SELECT COUNT(*), ROUND(AVG(last_match_score),2),"
    " (SELECT last_match_score FROM job_archive ORDER BY last_match_score LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM job_archive)),"
    " ROUND(100.0*SUM(CASE WHEN last_match_score>=50 THEN 1 ELSE 0 END)/COUNT(*),0),"
    " ROUND(100.0*SUM(CASE WHEN last_match_score>=60 THEN 1 ELSE 0 END)/COUNT(*),0)"
    " FROM job_archive"
).fetchone()
print(f"TOTAL archives: n={n}   avg=%{avg}   med=%{med}   >=%50=%{p50}   >=%60=%{p60}")

print("\n🔥 SON EKLENEN 10 İLAN (LinkedIn 2025 canlı çekim):")
cols = [r[1] for r in c.execute("PRAGMA table_info(job_archive)").fetchall()]
# find url-like cols
url_cols = [x for x in cols if "url" in x.lower() or "link" in x.lower()] or [None]
url_col = url_cols[0]
has_apply = url_col is not None
apply_select = f"{url_col}," if has_apply else "metadata AS _m,"
q = (
    "SELECT last_match_score, title, company_name, location, source_platform, "
    f"{apply_select} last_recommendation, last_seen_at"
    " FROM job_archive ORDER BY last_seen_at DESC LIMIT 10"
)
for i, row in enumerate(c.execute(q).fetchall(), 1):
    if has_apply:
        sc, ti, co, lo, sp, au, rec, ls = row
    else:
        sc, ti, co, lo, sp, _m, rec, ls = row
        au = None
        import json as _json
        try:
            md = _m and _json.loads(_m) or {}
            for k in ("apply_url", "source_url", "url", "link"):
                if isinstance(md, dict) and k in md and md[k]:
                    au = md[k]; break
        except Exception:
            pass
    print(f"  {i:2d}. [%{float(sc):.0f}] {(ti or '')[:62]!r}")
    print(f"      @ {(co or '')[:30]!r}   {(lo or '')[:22]!r}  {str(sp):<22s}  {(rec or '')[:35]}")
    if au:
        print(f"      URL: {(str(au) or '')[:110]}")
    print(f"      seen: {ls}")
c.close()
