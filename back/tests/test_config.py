import unittest
from pathlib import Path

from app.core.config import BACK_DIR, FRONTEND_DIST, PROJECT_DIR, Settings


class PathConfigurationTests(unittest.TestCase):
    def test_resolves_project_directories_from_core_package(self):
        project_dir = Path(__file__).resolve().parents[2]

        self.assertEqual(PROJECT_DIR, project_dir)
        self.assertEqual(BACK_DIR, project_dir / "back")
        self.assertEqual(FRONTEND_DIST, project_dir / "front" / "dist")

    def test_settings_derive_paths_from_data_dir(self):
        settings = Settings(data_dir=Path("C:/dados"), frontend_dist=Path("C:/front"))

        self.assertEqual(settings.database_path, Path("C:/dados/vigiapet.sqlite3"))
        self.assertEqual(settings.model_path, Path("C:/dados/models/yolox_tiny.onnx"))
        self.assertEqual(settings.clip_dir, Path("C:/dados/clips"))
        self.assertEqual(settings.log_dir, Path("C:/dados/logs"))

    def test_migrates_legacy_database_name_once(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(data_dir=Path(directory), frontend_dist=Path(directory))
            legacy = settings.data_dir / "monitorapet.sqlite3"
            legacy.write_bytes(b"dados antigos")
            settings.ensure_directories()
            self.assertFalse(legacy.exists())
            self.assertEqual(settings.database_path.read_bytes(), b"dados antigos")
            legacy.write_bytes(b"outro")
            settings.ensure_directories()
            self.assertEqual(settings.database_path.read_bytes(), b"dados antigos")


if __name__ == "__main__":
    unittest.main()
