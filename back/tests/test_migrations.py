import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.infra.database.database import Database


class MigrationTests(unittest.TestCase):
    def test_applies_each_migration_once(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.sqlite3")

            database.migrate()
            database.migrate()

            with closing(sqlite3.connect(database.path)) as connection:
                versions = connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }

            self.assertEqual(versions, [(1,), (2,), (3,)])
            self.assertTrue({"cameras", "zones", "events", "human_reviews"} <= tables)
            with closing(sqlite3.connect(database.path)) as connection:
                event_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(events)")
                }
            self.assertIn("corrected_zone_type", event_columns)


if __name__ == "__main__":
    unittest.main()
