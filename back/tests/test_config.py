import unittest
from pathlib import Path

from app.core.config import BACK_DIR, FRONTEND_DIST, PROJECT_DIR


class PathConfigurationTests(unittest.TestCase):
    def test_resolves_project_directories_from_core_package(self):
        project_dir = Path(__file__).resolve().parents[2]

        self.assertEqual(PROJECT_DIR, project_dir)
        self.assertEqual(BACK_DIR, project_dir / "back")
        self.assertEqual(FRONTEND_DIST, project_dir / "front" / "dist")

    def test_migrates_legacy_database_name_once(self):
        import tempfile
        from unittest.mock import patch

        from app.core import config

        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            legacy = data_dir / "monitorapet.sqlite3"
            current = data_dir / "vigiapet.sqlite3"
            legacy.write_bytes(b"dados antigos")
            with patch.object(config, "DATABASE_PATH", current), patch.object(config, "LEGACY_DATABASE_PATHS", (legacy,)):
                config._migrate_legacy_database()
                self.assertFalse(legacy.exists())
                self.assertEqual(current.read_bytes(), b"dados antigos")
                # Com o banco novo presente, um arquivo antigo remanescente é deixado em paz.
                legacy.write_bytes(b"outro")
                config._migrate_legacy_database()
                self.assertEqual(current.read_bytes(), b"dados antigos")


if __name__ == "__main__":
    unittest.main()
