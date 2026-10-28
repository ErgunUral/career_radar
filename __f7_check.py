from __future__ import annotations
import os, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).parent / "apps" / "api"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.core.database import init_database
from app.core.config import get_settings
from app.domains.watchers.db_repository import db_repository
from app.domains.watchers.discovery import LiveJobDiscoveryService

init_database()
settings = get_settings()
print(f"DEBUG: settings.database_url = {settings.database_url!r}")
raw = settings.database_url.replace("sqlite:///", "")
if raw.startswith("./"):
    raw = str(ROOT / raw[2:])
print(f"DEBUG: sqlite path = {raw!r}")
print(f"DEBUG: parent var mı? {Path(raw).parent.exists()}")
cnx = sqlite3.connect(raw)
cx = cnx.cursor()
cx.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cx.fetchall()]
print("TABLES:", tables)
print("operation_logs EXISTS:", "operation_logs" in tables)

rec = db_repository.log_event(
    level="INFO", source="scheduler",
    message="Test log · canlı DB INSERT doğrulaması",
    user_id="default-user", watcher_id=None,
    metadata={"test": True, "faz": 7, "script": "f7_check_db.py"}
)
print(f"INSERT OK: id={rec.id} level={rec.level} source={rec.source}")

cx.execute("SELECT id, timestamp, level, source, user_id, substr(message,1,60) FROM operation_logs ORDER BY id DESC LIMIT 3")
for r in cx.fetchall():
    print("  SQL:", r)
cnx.close()

# Playwright storage_state
disc = LiveJobDiscoveryService(timeout_seconds=0.5)
sp = disc.storage_state_path
print(f"\nstorage_state_path = {sp}")
if sp and Path(sp).exists():
    from pathlib import Path
    p = Path(sp)
    print(f"  Boyut: {p.stat().st_size} bytes · Mevcut: {p.exists()}")
    print(f"  HEAD 120 bytes: {p.read_text()[:120]!r}")
print("\n✅ F7_2 DB checks passed.")
