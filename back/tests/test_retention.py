import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.domain.errors import InvalidDomainValueError
from app.infra.media.media_cleanup import MediaCleanup
from app.infra.media.recording_reader import index_path_for
from app.infra.repositories.recording_repository import RecordingRepository
from app.infra.repositories.settings_repository import SettingsRepository
from app.services.event.retention import MediaRetentionService
from tests.test_monitoring import build_repositories, square_zone

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.directory.name)
        self.database, self.camera_repository, self.zone_repository, self.event_repository = build_repositories(self.directory.name)
        self.recordings = RecordingRepository(self.database)
        self.settings = SettingsRepository(self.database)
        self.camera = self.camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
        self.zone = self.zone_repository.create(square_zone(self.camera["id"], "Comida", "FOOD", 0))
        self.service = MediaRetentionService(
            self.settings, self.event_repository, self.recordings, MediaCleanup(self.data_dir), now=lambda: NOW
        )

    def tearDown(self):
        self.directory.cleanup()

    def _file(self, relative):
        path = self.data_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        return path

    def _event(self, days_ago, snapshot, capture=None):
        started = (NOW - timedelta(days=days_ago)).isoformat()
        return self.event_repository.create_detected_event(
            self.camera["id"], self.zone["id"], started, started, 0.9, snapshot, "CAT", capture
        )

    def test_default_retention_and_bounds(self):
        self.assertEqual(self.service.retention_days(), 7)
        self.assertEqual(self.service.set_retention_days(30), 30)
        self.assertEqual(self.service.view(), {"retention_days": 30})
        with self.assertRaises(InvalidDomainValueError):
            self.service.set_retention_days(0)

    def test_removes_media_older_than_retention_but_keeps_events_and_references(self):
        old_snapshot = self._file("snapshots/old.jpg")
        old_capture = self._file("pets/captures/old.jpg")
        kept_capture = self._file("pets/captures/ref.jpg")
        new_snapshot = self._file("snapshots/new.jpg")
        old_event = self._event(10, "snapshots/old.jpg", "pets/captures/old.jpg")
        referenced = self._event(12, None, "pets/captures/ref.jpg")
        new_event = self._event(2, "snapshots/new.jpg")
        self.database.execute(
            "INSERT INTO pets (id, name, species, description, created_at, updated_at) VALUES ('p', 'P', 'CAT', '', 'n', 'n')"
        )
        self.database.execute(
            "INSERT INTO pet_reference_images (id, pet_id, event_id, image_path, created_at) VALUES ('r', 'p', ?, 'pets/captures/ref.jpg', 'n')",
            (referenced,),
        )

        result = self.service.run()

        self.assertEqual(result.media_removed, 2)
        self.assertFalse(old_snapshot.exists())
        self.assertFalse(old_capture.exists())
        self.assertTrue(kept_capture.exists())
        self.assertTrue(new_snapshot.exists())
        events = {event["id"]: event for event in self.event_repository.list(camera_id=self.camera["id"])}
        self.assertEqual(len(events), 3)
        self.assertIsNone(events[old_event]["snapshot_path"])
        self.assertIsNone(events[old_event]["pet_capture_path"])
        self.assertEqual(events[referenced]["pet_capture_path"], "pets/captures/ref.jpg")
        self.assertEqual(events[new_event]["snapshot_path"], "snapshots/new.jpg")

    def test_removes_only_app_owned_recording_files(self):
        owned = self._file("recordings/cam/old.h264")
        index_path_for(owned).write_text(json.dumps({"timestamps": []}))
        outside = Path(self.directory.name).parent / "vigiapet-outside-test.mp4"
        outside.write_bytes(b"x")
        try:
            for path in (owned, outside):
                self.recordings.create({
                    "camera_id": self.camera["id"], "origin": "FOLDER", "path": str(path), "fingerprint": path.name,
                    "started_at": (NOW - timedelta(days=9)).isoformat(), "ended_at": (NOW - timedelta(days=9)).isoformat(),
                })
            recent = self._file("recordings/cam/new.h264")
            self.recordings.create({
                "camera_id": self.camera["id"], "origin": "CAMERA", "path": str(recent), "fingerprint": "new",
                "started_at": (NOW - timedelta(days=1)).isoformat(), "ended_at": (NOW - timedelta(days=1)).isoformat(),
            })

            result = self.service.run()

            self.assertEqual(result.recordings_removed, 1)
            self.assertFalse(owned.exists())
            self.assertFalse(index_path_for(owned).exists())
            self.assertTrue(outside.exists())
            self.assertTrue(recent.exists())
            self.assertEqual(len(self.recordings.list(self.camera["id"])), 3)
        finally:
            outside.unlink(missing_ok=True)

    def test_pending_review_queue_is_chronological(self):
        for days_ago in (3, 1, 2):
            event_id = self._event(days_ago, None)
            self.event_repository.finish_detected_event(event_id, (NOW - timedelta(days=days_ago)).isoformat(), 5, "CAT_LEFT_ZONE")

        pending = self.event_repository.list(pending_review=True)
        history, _ = self.event_repository.search(1, 10)

        self.assertEqual([event["started_at"] for event in pending], sorted(event["started_at"] for event in pending))
        self.assertEqual([event["started_at"] for event in history], sorted((event["started_at"] for event in history), reverse=True))


if __name__ == "__main__":
    unittest.main()
