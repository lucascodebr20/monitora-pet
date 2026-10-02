from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parent


def run_migrations(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               applied_at TEXT NOT NULL
           )"""
    )
    applied = {
        row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        version = int(path.stem.split("_", 1)[0])
        if version in applied:
            continue
        name = path.stem.replace("'", "''")
        applied_at = datetime.now(timezone.utc).isoformat().replace("'", "''")
        script = path.read_text(encoding="utf-8")
        try:
            connection.executescript(
                f"BEGIN IMMEDIATE;\n{script}\n"
                f"INSERT INTO schema_migrations(version, name, applied_at) "
                f"VALUES ({version}, '{name}', '{applied_at}');\nCOMMIT;"
            )
        except sqlite3.Error:
            connection.rollback()
            raise
