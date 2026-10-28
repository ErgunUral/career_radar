import sqlite3, sys, pathlib, json
sys.path.insert(0, "apps/api")
from app.core.config import get_settings
db = pathlib.Path(get_settings().database_url.replace("sqlite:///", "")).resolve()
c = sqlite3.connect(db)
# 25 adet 8 Ağu KariyerNET platformu olanları bul — metadata'ya source_url var mı?
rows_kn = c.execute(
    "SELECT id, job_id, title, company_name, location, metadata FROM job_archive "
    "WHERE source_platform NOT LIKE '%linkedin%' LIMIT 30"
).fetchall()
print(f"LinkedIn OLMAYAN kayıt sayısı: {len(rows_kn)}")
for r in rows_kn:
    (rid, jid, t, co, lo, md) = r
    try:
        d = json.loads(md) if isinstance(md, str) else md
        keys = sorted(d.keys()) if isinstance(d, dict) else []
        urls_in_md = []
        if isinstance(d, dict):
            for mk in keys:
                mv = d[mk]
                if isinstance(mv, str) and mv.startswith("http"):
                    urls_in_md.append(f"{mk}={mv[:120]}")
        print(f"  id={rid:<3d} job_id={jid!r:<30s} platform=NON-LI   "
              f"title={t[:40]!r}   md_keys={keys}   urls_in_md={urls_in_md}")
    except Exception as e:
        print(f"  id={rid}  PARSEERR {e}")

# TÜM platformları say
print("\nPlatform dağılımı:")
for p, n in c.execute("SELECT source_platform, COUNT(*) FROM job_archive GROUP BY 1 ORDER BY 2 DESC").fetchall():
    print(f"  {str(p):<30s}  n={n}")
c.close()
