import sys
import httpx
import sqlite3
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import get_settings  # noqa: E402

s = get_settings()
storage_dir = Path(s.storage_dir)
db_url = s.database_url
db_path = Path(db_url.replace("sqlite:///", "")) if "sqlite://" in db_url else storage_dir / "careerradar.db"
ss_path = storage_dir / "storage_state.json"

print("=" * 72)
print("  CareerRadar AI · Final Smoke Test (GERÇEK Settings import ile)")
print("=" * 72)

print(f"\n  settings.storage_dir = {storage_dir}")
print(f"  settings.database_url = {db_url}")
print(f"  resolved db_path      = {db_path}")

# 1) Storage dosyaları
print("\n[1/3] Storage:")
for p in [ss_path, db_path]:
    ok = p.exists()
    sz = p.stat().st_size if ok else 0
    print(f"   · {p.name:32s} exists={ok}  size={sz:,} bytes")

# 2) SQLite
print("\n[2/3] SQLite tables & counts (TEK DB):")
conn = sqlite3.connect(db_path)
c = conn.cursor()
for (t,) in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall():
    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    bar = "█" * max(0, min(50, n // 3 if n else 0))
    print(f"   · {t:30s} {n:>6}  {bar}")
conn.close()

# 3) Live endpoints
print("\n[3/3] Live endpoints:")
checks = []
for path in ["/health", "/api/v1/health", "/api/v1/matching/health"]:
    try:
        r = httpx.get(f"http://127.0.0.1:8000{path}", timeout=4)
        if r.status_code == 200:
            checks.append(("API health", f"http://127.0.0.1:8000{path}"))
            break
    except Exception:
        pass
if not checks:
    checks.append(("API health", "http://127.0.0.1:8000/health"))
checks.extend([
    ("API watchers(3)", "http://127.0.0.1:8000/api/v1/watchers?limit=3"),
    ("UI 8501 page", "http://127.0.0.1:8501/"),
])
all_ok = True
for name, url in checks:
    try:
        r = httpx.get(url, timeout=8, follow_redirects=True)
        ok = r.status_code == 200
        all_ok = all_ok and ok
        st = "✅" if ok else "⚠️"
        print(f"   {st} {name:16s}  HTTP {r.status_code}")
        if ok and "watchers" in name:
            ws = r.json()
            for w in ws[-3:]:
                nm = str(w.get("name", ""))[:42]
                print(f"         · {w.get('id','?')[:14]} active={w.get('is_active')}  {nm!r}")
        elif "UI" in name:
            print(f"         bytes={len(r.content)}")
    except Exception as e:
        all_ok = False
        print(f"   ❌ {name:16s}  HATA: {e!r}")

# Özet
print("\n" + "=" * 72)
print(f"  GENEL SONUÇ: {'✅ TAMAM · TEK DB · CANLI · SAGLIKLI' if all_ok else '⚠️ BAZI ÖĞELER EKSİK'}")
print("=" * 72)
