#!/usr/bin/env python3
"""F9 Helper: DBden doğrudan watcher metadata.source_urls güncelle."""
import json
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).parent / "apps" / "api" / "careerradar.db"


def main() -> int:
    wid = sys.argv[1] if len(sys.argv) > 1 else Path("/tmp/_f9_wid.txt").read_text().strip()
    source_urls = [
        "https://www.kariyer.net/is-ilanlari?kw=test+yoneticisi&cs=35689",
        "https://www.kariyer.net/is-ilanlari?kw=qa+manager&cs=35689",
        "https://www.yenibiri.com/is-ilanlari?q=test+yoneticisi",
        "https://www.yenibiri.com/is-ilanlari?q=test+manager",
    ]
    print(f"DB: {DB} (exists={DB.exists()})")
    print(f"Watcher: {wid}")
    cnx = sqlite3.connect(DB)
    cnx.row_factory = sqlite3.Row
    row = cnx.execute("SELECT metadata FROM watchers WHERE id = ?", (wid,)).fetchone()
    if not row:
        print("❌ Watcher bulunamadı!")
        return 1
    meta_raw = row["metadata"] or "{}"
    try:
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else dict(meta_raw or {})
    except Exception:
        meta = {}
    print(f"  Önce metadata: keys={list(meta.keys())}  src_urls = {(meta or {}).get('source_urls')}")
    meta["source_urls"] = source_urls
    cnx.execute("UPDATE watchers SET metadata = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(meta, ensure_ascii=False), wid))
    cnx.commit()
    row2 = cnx.execute("SELECT metadata, search_criteria FROM watchers WHERE id = ?", (wid,)).fetchone()
    try:
        meta2 = json.loads(row2["metadata"])
    except Exception:
        meta2 = {}
    print(f"  Sonra metadata.source_urls len = {len(meta2.get('source_urls', []))}")
    for u in (meta2 or {}).get("source_urls", []):
        print(f"    · {u}")
    print("✅ Tamamlandı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
