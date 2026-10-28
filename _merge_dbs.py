import sqlite3
from pathlib import Path

root = Path.cwd()
target = root / "apps" / "api" / "app" / "storage" / "careerradar.db"
api_db = root / "apps" / "api" / "careerradar.db"
root_db = root / "careerradar.db"

print(f"Hedef : {target}  (exists={target.exists()})")
print(f"API DB: {api_db}   (exists={api_db.exists()})")

if not target.exists() and root_db.exists():
    target.write_bytes(root_db.read_bytes())
    print(f"  → Root DB hedefe kopyalandı ({target.stat().st_size} bytes)")

if api_db.exists():
    dest = sqlite3.connect(target)
    try:
        dest.execute(f"ATTACH DATABASE '{api_db}' AS apidb")

        t_exists = dest.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='operation_logs'"
        ).fetchone()
        if not t_exists:
            schema_r = dest.execute(
                "SELECT sql FROM apidb.sqlite_master WHERE name='operation_logs'"
            ).fetchone()
            if schema_r:
                dest.execute(schema_r[0])
                print("  → operation_logs tablosu hedefe yaratıldı (şema API'den)")

        cols_r = dest.execute("PRAGMA table_info(operation_logs)").fetchall()
        colnames = [c[1] for c in cols_r]
        cols_sql = ",".join([f'"{c}"' for c in colnames])
        placeholders = ",".join(["?"] * len(colnames))

        before = dest.execute("SELECT COUNT(*) FROM operation_logs").fetchone()[0]
        api_n = dest.execute("SELECT COUNT(*) FROM apidb.operation_logs").fetchone()[0]
        print(f"  → operation_logs: hedef(önce)={before}  API={api_n}")

        rows = dest.execute(f"SELECT {cols_sql} FROM apidb.operation_logs").fetchall()
        for row in rows:
            try:
                dest.execute(
                    f"INSERT OR IGNORE INTO operation_logs ({cols_sql}) VALUES ({placeholders})",
                    row,
                )
            except Exception as e:
                pass
        dest.commit()
        after = dest.execute("SELECT COUNT(*) FROM operation_logs").fetchone()[0]
        print(f"  → operation_logs: hedef(sonra)={after}  (eklenen={after - before})")
    finally:
        dest.close()

# Eski dosyaları .bak yap
for old in [root_db, api_db]:
    if old.exists():
        bak = old.with_suffix(old.suffix + ".ROOT.bak" if "root" in str(old).lower() else old.suffix + ".API.bak")
        if not bak.exists():
            old.rename(bak)
            print(f"  → {old} → {bak.name} (backup)")
        else:
            old.unlink()
            print(f"  → {old} (zaten backup var, silindi)")

# Son DB özet
conn = sqlite3.connect(target)
c = conn.cursor()
print("\n=== HEP SİLİNDİKTEN SONRA (TEK DB) ===")
for (t,) in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall():
    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    bar = "█" * max(0, min(50, n // 3 if n else 0))
    print(f"  {t:32s} {n:>6}  {bar}")
conn.close()
print(f"\nDosya boyutu: {target.stat().st_size:,} bytes")
