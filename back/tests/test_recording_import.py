import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging_setup import reset_logging
from app.infra.media.filename_time import start_time_from_name
from app.main import create_app


class FilenameTimeTests(unittest.TestCase):
    def test_parses_common_camera_filename_patterns(self):
        expected = datetime(2026, 10, 5, 8, 30, 15).astimezone().astimezone(timezone.utc)
        for name in (
            "20261005_083015.mp4",
            "2026-10-05 08-30-15.mkv",
            "REC_20261005083015_1.avi",
            "ch01_2026.10.05_08.30.15.mp4",
            "2026-10-05T08:30:15.mp4",
        ):
            self.assertEqual(start_time_from_name(Path(name)), expected, name)

    def test_returns_none_without_timestamp(self):
        self.assertIsNone(start_time_from_name(Path("video_final.mp4")))
        self.assertIsNone(start_time_from_name(Path("IMG_1234.mp4")))


class RecordingRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.settings = Settings(data_dir=root / "data", frontend_dist=root / "dist")
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()
        self.folder = root / "sd"
        self.folder.mkdir()
        self._write_video(self.folder / "20261005_080000.mp4")
        self._write_video(self.folder / "notes.txt")

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        reset_logging()
        self.temp.cleanup()

    @staticmethod
    def _write_video(path: Path) -> None:
        import numpy as np
        from app.infra.media.clip_store import ClipStore

        if path.suffix != ".mp4":
            path.write_text("x")
            return
        store = ClipStore(path.parent, path.parent)
        encoded = store.encode(np.zeros((120, 160, 3), dtype=np.uint8))
        relative = store.save([encoded] * 6, datetime(2026, 1, 1, tzinfo=timezone.utc), fps=3.0)
        (path.parent / relative).replace(path)

    def test_manual_camera_folder_import_and_time_adjustment(self):
        created = self.client.post("/api/cameras/manual", json={"name": "Cartão da sala"})
        self.assertEqual(created.status_code, 201)
        camera = created.json()
        self.assertEqual(camera["source_kind"], "MANUAL")
        self.assertEqual(camera["ip"], "")
        self.assertEqual(camera["recording_support"], "NONE")
        self.assertEqual(self.client.post(f"/api/cameras/{camera['id']}/connect", json={}).status_code, 422)

        imported = self.client.post("/api/recordings/import", json={"camera_id": camera["id"], "path": str(self.folder)})
        self.assertEqual(imported.status_code, 201)
        recordings = imported.json()["recordings"]
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0]["time_source"], "FILENAME")
        self.assertEqual(recordings[0]["status"], "PENDING")
        expected_start = datetime(2026, 10, 5, 8, 0, 0).astimezone().astimezone(timezone.utc)
        self.assertEqual(recordings[0]["started_at"], expected_start.isoformat())
        self.assertEqual(recordings[0]["ended_at"], (expected_start + timedelta(seconds=2)).isoformat())

        again = self.client.post("/api/recordings/import", json={"camera_id": camera["id"], "path": str(self.folder)})
        self.assertEqual(again.json()["recordings"][0]["id"], recordings[0]["id"])
        self.assertEqual(len(self.client.get(f"/api/recordings?camera_id={camera['id']}").json()["recordings"]), 1)

        adjusted = self.client.patch(
            f"/api/recordings/{recordings[0]['id']}", json={"started_at": "2026-10-05T10:00:00+00:00"}
        )
        self.assertEqual(adjusted.status_code, 200)
        self.assertEqual(adjusted.json()["time_source"], "MANUAL")
        self.assertEqual(adjusted.json()["ended_at"], "2026-10-05T10:00:02+00:00")

        preview = self.client.get(f"/api/cameras/{camera['id']}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/jpeg")

    def test_watched_folder_lifecycle_and_scan(self):
        camera = self.client.post("/api/cameras/manual", json={"name": "Cartão"}).json()
        missing = self.client.post("/api/recordings/folders", json={"camera_id": camera["id"], "path": str(self.folder / "nao")})
        self.assertEqual(missing.status_code, 404)
        folder = self.client.post("/api/recordings/folders", json={"camera_id": camera["id"], "path": str(self.folder)})
        self.assertEqual(folder.status_code, 201)
        self.assertEqual(
            self.client.post("/api/recordings/folders", json={"camera_id": camera["id"], "path": str(self.folder)}).status_code,
            409,
        )

        scanned = self.client.post(f"/api/recordings/folders/{folder.json()['id']}/scan")
        self.assertEqual(scanned.status_code, 200)
        self.assertEqual(len(scanned.json()["recordings"]), 1)
        listed = self.client.get(f"/api/recordings/folders?camera_id={camera['id']}").json()["folders"]
        self.assertIsNotNone(listed[0]["last_scanned_at"])
        self.assertEqual(self.client.delete(f"/api/recordings/folders/{folder.json()['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/recordings/folders").json(), {"folders": []})

    def test_preview_without_connection_or_recordings_is_404(self):
        camera = self.client.post("/api/cameras/manual", json={"name": "Vazia"}).json()
        self.assertEqual(self.client.get(f"/api/cameras/{camera['id']}/preview").status_code, 404)

    @patch("app.services.camera.service.resolve_connection_urls", return_value=["rtsp://192.168.1.9/x"])
    def test_manual_camera_can_become_network_camera(self, _urls):
        camera = self.client.post("/api/cameras/manual", json={"name": "Cartão"}).json()
        with patch("app.services.camera.service.CameraService._remember"):
            converted = self.client.post(
                f"/api/cameras/{camera['id']}/convert", json={"ip": "192.168.1.9", "username": "a", "password": "b"}
            )
        self.assertEqual(converted.status_code, 200)
        self.assertEqual(converted.json()["source_kind"], "NETWORK")
        self.assertEqual(converted.json()["ip"], "192.168.1.9")
        self.assertEqual(self.client.post(f"/api/cameras/{camera['id']}/convert", json={"ip": "192.168.1.9"}).status_code, 422)

    def test_two_manual_cameras_do_not_collide(self):
        first = self.client.post("/api/cameras/manual", json={"name": "A"})
        second = self.client.post("/api/cameras/manual", json={"name": "B"})
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertEqual(len(self.client.get("/api/cameras").json()["cameras"]), 2)


if __name__ == "__main__":
    unittest.main()
