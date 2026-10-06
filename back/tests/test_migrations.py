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

            self.assertEqual(versions, [(1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,)])
            self.assertTrue({"cameras", "zones", "events", "human_reviews"} <= tables)
            with closing(sqlite3.connect(database.path)) as connection:
                event_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(events)")
                }
            self.assertIn("corrected_zone_type", event_columns)
            self.assertIn("automatically_identified_pet_id", event_columns)
            self.assertIn("pet_identification_confidence", event_columns)
            self.assertIn("pet_identification_method", event_columns)
            self.assertTrue({
                "pet_identification_analyses",
                "pet_identification_scores",
                "pet_identification_calibrations",
            } <= tables)
            with closing(sqlite3.connect(database.path)) as connection:
                analysis_columns = {row[1] for row in connection.execute("PRAGMA table_info(pet_identification_analyses)")}
                calibration_columns = {row[1] for row in connection.execute("PRAGMA table_info(pet_identification_calibrations)")}
            self.assertIn("method", analysis_columns)
            self.assertIn("method", calibration_columns)


if __name__ == "__main__":
    unittest.main()
