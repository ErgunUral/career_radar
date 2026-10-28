import sys
from pathlib import Path
ROOT = Path(__file__).parent / "apps" / "api"
sys.path.insert(0, str(ROOT))

from app.api.routes.watchers import watchers_router, logs_router, notifications_router, archive_router
print("[1] watchers_router prefix:", watchers_router.prefix, "routes:", len(watchers_router.routes))
print("[2] archive_router  prefix:", archive_router.prefix,  "routes:", len(archive_router.routes))
print("[3] notifications   prefix:", notifications_router.prefix, "routes:", len(notifications_router.routes))
print("[4] logs_router     prefix:", logs_router.prefix,    "routes:", len(logs_router.routes))
for r in logs_router.routes:
    print("    route LOG:", getattr(r, "path", None), getattr(r, "methods", None))

print()
from app.main import app
print("[5] MAIN app.routes içinde 'log' / 'logs' geçen path:")
for route in app.routes:
    p = getattr(route, "path", "")
    if "log" in p.lower():
        print("   MAIN route LOG:", p, getattr(route, "methods", None))

print()
print("[6] MAIN app tüm prefix ROUTES (toplam 8):")
prefixes = set()
for r in app.routes:
    p = getattr(r, "path", "")
    if p.startswith("/api/v1/"):
        parts = p.split("/")
        if len(parts) >= 4:
            prefixes.add("/" + "/".join(parts[1:4]))
for pr in sorted(prefixes):
    print("  ", pr)
