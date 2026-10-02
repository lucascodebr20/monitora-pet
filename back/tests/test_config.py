import unittest
from pathlib import Path

from app.core.config import BACK_DIR, FRONTEND_DIST, PROJECT_DIR


class PathConfigurationTests(unittest.TestCase):
    def test_resolves_project_directories_from_core_package(self):
        project_dir = Path(__file__).resolve().parents[2]

        self.assertEqual(PROJECT_DIR, project_dir)
        self.assertEqual(BACK_DIR, project_dir / "back")
        self.assertEqual(FRONTEND_DIST, project_dir / "front" / "dist")


if __name__ == "__main__":
    unittest.main()
