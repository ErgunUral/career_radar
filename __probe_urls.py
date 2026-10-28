import sqlite3, sys, pathlib, json, re
sys.path.insert(0, "apps/api")
from app.core.config import get_settings
db = pathlib.Path(get_settings().database_url.replace("sqlite:///", "")).resolve()
print(f"DB={db}  size={db.stat().st_size/1024:.0f} KB\n")
c = sqlite3.connect(db)

cols = c.execute("PRAGMA table_info(job_archive)").fetchall()
print("[PRAGMA table_info(job_archive)]:")
for ci in cols:
    print(f"  cid={ci[0]:<2d}  name={ci[1]:<26s}  type={ci[2]:<14s}  notnull={ci[3]}  pk={ci[5]}")

url_cols = [ci[1] for ci in cols if "url" in ci[1].lower() or "link" in ci[1].lower()]
print(f"\nURL benzeri kolonlar: {url_cols}\n")

# Sample 3 kayıt: kariyernet (id 1-25) + linkedin (son 3)
print("[SON 3 LinkedIn + İLK 3 KariyerNET kayıt · raw kolonlar]:")
rows = c.execute("SELECT * FROM job_archive ORDER BY id DESC LIMIT 3").fetchall() + c.execute("SELECT * FROM job_archive ORDER BY id ASC LIMIT 3").fetchall()
col_names = [ci[1] for ci in cols]
for r in rows:
    d = dict(zip(col_names, r))
    print(f"\n  id={d['id']:<4d} platform={str(d['source_platform']):<22s}  "
          f"job_id={str(d.get('job_id',''))[:30]!r}  title={str(d.get('title',''))[:45]!r}")
    for k in list(d.keys()):
        v = d[k]
        if v is None or v == "":
            continue
        if k in ("metadata",):
            try:
                md = json.loads(v) if isinstance(v,str) else v
                keys = sorted(md.keys()) if isinstance(md, dict) else []
                urls_in_md = []
                if isinstance(md, dict):
                    for mk in keys:
                        mv = md[mk]
                        if isinstance(mv, str) and (mv.startswith("http") or "url" in mk.lower() or "link" in mk.lower()):
                            urls_in_md.append(f"{mk}={mv[:100]}")
                print(f"    metadata keys={keys}   urls_in_md={urls_in_md}")
            except Exception as e:
                print(f"    metadata PARSEERR {e}  raw[:200]={str(v)[:200]!r}")
        elif "url" in k.lower() or "link" in k.lower() or k == "job_id" or k == "apply_url":
            print(f"    {k} = {str(v)[:140]!r}")

# platforma göre job_id format örüntüleri
print("\n[Platform job_id format örüntüleri (TOP 3 örnek):")
for p, in c.execute("SELECT DISTINCT source_platform FROM job_archive").fetchall():
    jids = c.execute("SELECT job_id FROM job_archive WHERE source_platform=? LIMIT 5", (p,)).fetchall()
    print(f"  platform={p!s:<22s}  job_id örnekleri:")
    for (j,) in jids:
        print(f"    · {j!r}")

c.close()
