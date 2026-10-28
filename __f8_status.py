#!/usr/bin/env python3
"""Faz 8 durum özeti: Archive + Operation Log SQL kanıtı."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))
from app.core.database import engine  # noqa: E402


def main() -> None:
    db_path = str(engine.url.database)
    print(f"SQLite DB: {db_path}")
    cnx = sqlite3.connect(db_path)
    cnx.row_factory = sqlite3.Row

    cur = cnx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [r["name"] for r in cur.fetchall()]
    print(f"Tablolar ({len(tables)} adet):")
    for t in tables:
        cur = cnx.execute(f'SELECT COUNT(*) as cnt FROM "{t}"')
        print(f"  - {t:<30} COUNT={cur.fetchone()['cnt']}")
    print()

    print("=== job_archive GROUP BY user_id ===")
    cur = cnx.execute(
        "SELECT COALESCE(user_id, 'NULL') as uid, COUNT(*) as cnt FROM job_archive GROUP BY uid ORDER BY cnt DESC"
    )
    for r in cur.fetchall():
        print(f"  user_id={r['uid']!r:<15} COUNT={r['cnt']}")
    cur = cnx.execute("SELECT COUNT(*) as cnt FROM job_archive")
    print(f"  TOPLAM Archive: {cur.fetchone()['cnt']}")
    print()

    print("=== Son 5 Archive (created_at DESC) ===")
    cur = cnx.execute(
        "SELECT id, user_id, title, company, match_score, source_platform, created_at "
        "FROM job_archive ORDER BY created_at DESC LIMIT 5"
    )
    for r in cur.fetchall():
        title = (r["title"] or "")[:70]
        co = (r["company"] or "")[:25]
        score = r["match_score"] or 0
        uid = r["user_id"] or "-"
        ts = (r["created_at"] or "")[:16]
        print(f"  [{ts}] u={uid:<12} %{score:<4.0f} @{co:<25} | {title}")

    print()
    log_tables = [t for t in tables if "log" in t.casefold()]
    for lt in log_tables:
        print(f"=== Operation Log: {lt} (son 7 kayıt) ===")
        cur = cnx.execute(
            f'SELECT id, user_id, level, source, message, created_at FROM "{lt}" '
            "ORDER BY created_at DESC LIMIT 7"
        )
        rows = cur.fetchall()
        print(f"  Toplam COUNT = {len(rows)} rows / son 7:")
        for r in rows:
            uid = r["user_id"] or "-"
            lvl = r["level"] or "?"
            src = r["source"] or "?"
            msg = (r["message"] or "")[:90]
            ts = (r["created_at"] or "")[:16]
            print(f"  [{ts}] [{lvl:<5}] {src:<10} u={uid:<12} | {msg}")

    cnx.close()


if __name__ == "__main__":
    main()
