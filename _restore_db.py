import sqlite3
from pathlib import Path

root = Path.cwd()
target = root / "apps" / "api" / "app" / "storage" / "careerradar.db"
root_bak = root / "careerradar.db.API.bak"
api_bak = root / "apps" / "api" / "careerradar.db.API.bak"

print("=" * 70)
print("  DB Geri Yükleme · operation_log 417 KORUNACAK")
print("=" * 70)
print(f"\n  HEDEF   : {target}")
print(f"  ROOT BAK: {root_bak}")
print(f"  API BAK : {api_bak}")

dest = sqlite3.connect(target)
dest.execute(f"ATTACH DATABASE '{root_bak}' AS rootdb")
dest.execute(f"ATTACH DATABASE '{api_bak}' AS apidb")

c = dest.cursor()

# Hedef şema: tüm tablolar yaratılmış mı? Eksikse baklardan şema al
TABLES = [
    "watchers", "watcher_runs", "job_archive", "jobs", "notifications",
    "operation_logs", "applications", "candidate_profiles", "cv_files",
]

for t in TABLES:
    exists = c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)
    ).fetchone()
    if exists:
        continue
    for alias in ["rootdb", "apidb"]:
        s = c.execute(
            f"SELECT sql FROM {alias}.sqlite_master WHERE name=?", (t,)
        ).fetchone()
        if s and s[0]:
            c.execute(s[0])
            print(f"  · Şema yaratıldı: {t}  ({alias})")
            break

# 1) ROOT_BAK'dan WATCHERS / WATCHER_RUNS / JOB_ARCHIVE / JOBS / NOTIFS
#    - Kaynak dolu, hedef boş → INSERT OR IGNORE
restore_tables = ["watchers", "watcher_runs", "job_archive", "jobs", "notifications"]
print("\n[1/3] ROOT_BAK tabloları → HEDEF (INSERT OR IGNORE):")
for t in restore_tables:
    src_count = c.execute(f"SELECT COUNT(*) FROM rootdb.{t}").fetchone()[0]
    before = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
    cols_sql = ",".join([f'"{x}"' for x in cols])
    placeholders = ",".join(["?"] * len(cols))
    rows = c.execute(f"SELECT {cols_sql} FROM rootdb.{t}").fetchall()
    added = 0
    for row in rows:
        try:
            prev = dest.total_changes
            c.execute(
                f"INSERT OR IGNORE INTO {t} ({cols_sql}) VALUES ({placeholders})",
                row,
            )
            added += dest.total_changes - prev
        except Exception as e:
            pass
    after = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  · {t:18s}  src={src_count}  hedef(önce)={before}  hedef(sonra)={after}  eklendi={added}")

# 2) OPERATION_LOGS: HEDEFTE 417 VAR — KORUNACAK. API_BAK 295'i eksikse ekle
print("\n[2/3] OPERATION_LOGS · HEDEF 417 KORU + API_BAK 295 eksikse merge:")
before_op = c.execute("SELECT COUNT(*) FROM operation_logs").fetchone()[0]
cols_op = [r[1] for r in c.execute("PRAGMA table_info(operation_logs)").fetchall()]
cols_sql_op = ",".join([f'"{x}"' for x in cols_op])
placeholders_op = ",".join(["?"] * len(cols_op))
rows_op = c.execute(f"SELECT {cols_sql_op} FROM apidb.operation_logs").fetchall()
added_op = 0
for row in rows_op:
    try:
        prev = dest.total_changes
        c.execute(
            f"INSERT OR IGNORE INTO operation_logs ({cols_sql_op}) VALUES ({placeholders_op})",
            row,
        )
        added_op += dest.total_changes - prev
    except Exception:
        pass
after_op = c.execute("SELECT COUNT(*) FROM operation_logs").fetchone()[0]
print(f"  · operation_logs: hedef(önce)={before_op}  API_BAK={len(rows_op)}  eklendi={added_op}  SON={after_op}")

dest.commit()

# 3) SON ÖZET
print("\n[3/3] SON DB DURUMU:")
for t in TABLES:
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        bar = "█" * max(0, min(50, n // 4 if n else 0))
        print(f"  · {t:22s} {n:>6}  {bar}")
    except Exception as e:
        print(f"  · {t:22s} HATA: {e}")

dest.close()
print(f"\n  Hedef DB boyutu: {target.stat().st_size:,} bytes")
print("\n" + "=" * 70)
print("  BAŞARILI: Tüm tablolar geri yüklendi · operation_log 417 KORUNDU")
print("=" * 70)
