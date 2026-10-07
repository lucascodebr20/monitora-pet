import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.infra.repositories.recording_repository import RecordingRepository
from app.services.recordings.analyzer import RecordingBatchResult
from app.services.recordings.worker import ImportWorker
from tests.test_monitoring import build_repositories

START = datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)


class FakeImporter:
    def __init__(self):
        self.scanned = []
        self.folders = None

    def scan_watched_folders(self, camera_id=None):
        self.scanned.append(camera_id)
        return []


class FakeAnalyzer:
    def __init__(self, recordings):
        self.recordings = recordings
        self.calls = []

    def analyze_camera(self, camera_id, pending, should_stop=None, on_progress=None):
        self.calls.append((camera_id, [item["id"] for item in pending]))
        for item in pending:
            if on_progress:
                on_progress(item["id"], 5.0)
            self.recordings.set_status(item["id"], "DONE")
        return RecordingBatchResult(processed=len(pending))


class FakeSync:
    def __init__(self):
        self.calls = []

    def sync(self, camera_id):
        from app.services.recordings.camera_sync import CameraSyncResult

        self.calls.append(camera_id)
        return CameraSyncResult(downloaded=[{"id": "x"}])


class ImportWorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database, self.camera_repository, _, _ = build_repositories(self.directory.name)
        self.recordings = RecordingRepository(self.database)
        self.camera = self.camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
        self.states = []
        self.importer = FakeImporter()
        self.analyzer = FakeAnalyzer(self.recordings)
        self.sync = FakeSync()
        self.worker = ImportWorker(
            self.importer, self.analyzer, self.sync, self.recordings, self.camera_repository, on_state=self.states.append
        )

    def tearDown(self):
        self.worker.stop()
        self.directory.cleanup()

    def _recording(self, name, status="PENDING"):
        recording = self.recordings.create({
            "camera_id": self.camera["id"], "origin": "FOLDER", "path": f"C:/g/{name}", "fingerprint": name,
            "started_at": START.isoformat(), "ended_at": (START + timedelta(seconds=10)).isoformat(),
        })
        if status != "PENDING":
            self.recordings.set_status(recording["id"], status)
        return recording

    def test_start_resets_interrupted_recordings_and_processes_pending(self):
        interrupted = self._recording("a.mp4", "PROCESSING")
        pending = self._recording("b.mp4")

        self.worker.start()
        self.assertTrue(self.worker.wait_idle(timeout=5))

        self.assertEqual(self.recordings.get(interrupted["id"])["status"], "DONE")
        self.assertEqual(self.recordings.get(pending["id"])["status"], "DONE")
        self.assertEqual(self.analyzer.calls[0][0], self.camera["id"])
        self.assertEqual(set(self.analyzer.calls[0][1]), {interrupted["id"], pending["id"]})
        self.assertEqual(self.states, ["running", "idle"])
        state = self.worker.state()
        self.assertEqual(state["status"], "idle")
        self.assertEqual(state["last_result"], {"kind": "import", "processed": 2, "skipped": 0, "failed": 0, "events_before": 0})
        self.assertEqual(state["pending_recordings"], 0)
        self.assertEqual(self.importer.scanned, [None])

    def test_sync_job_downloads_then_analyzes_same_camera(self):
        self.worker.request_sync(self.camera["id"])
        self.worker.run_pending()

        self.assertEqual(self.sync.calls, [self.camera["id"]])
        self.assertEqual(self.importer.scanned, [self.camera["id"]])
        self.assertEqual(self.worker.state()["camera_name"], "Sala")

    def test_missing_model_leaves_recordings_pending_with_error(self):
        worker = ImportWorker(self.importer, None, self.sync, self.recordings, self.camera_repository)
        self._recording("a.mp4")

        worker.request_import()
        worker.run_pending()

        self.assertEqual(self.recordings.list(status="PENDING").__len__(), 1)
        self.assertIn("Modelo de IA ausente", worker.state()["error"])

    def test_duplicate_requests_collapse_into_one_job(self):
        self.worker.request_import()
        state = self.worker.request_import()

        self.assertEqual(state["queue"], 1)
        self.assertEqual(self.worker.cancel()["queue"], 0)


if __name__ == "__main__":
    unittest.main()
