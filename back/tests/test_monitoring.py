import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.domain.detection import Detection
from app.infra.database.database import Database
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.services.monitoring_service import MonitoringService


class FakeCameraManager:
    def latest_frame(self, camera_id):
        return np.zeros((240, 320, 3), dtype=np.uint8)

    def snapshot(self, camera_id):
        return b"jpeg"

    def connected_ids(self):
        return ["camera"]


class FakeDetector:
    def detect(self, frame):
        return [Detection(0.4, 0.4, 0.6, 0.6, 0.9)]


class OverlappingDetector:
    def detect(self, frame):
        return [Detection(0.7, 0.2, 0.98, 0.8, 0.89)]


class FakeSnapshotStore:
    def save(self, content, captured_at):
        return "snapshots/test.jpg"


class MonitoringTests(unittest.TestCase):
    def test_creates_event_when_cat_remains_inside_zone(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "monitoring.sqlite3")
            database.migrate()
            camera_repository = CameraRepository(database)
            zone_repository = ZoneRepository(database)
            event_repository = EventRepository(database)
            camera = camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
            zone_repository.create({
                "camera_id": camera["id"],
                "name": "Água",
                "type": "WATER",
                "polygon": ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)),
                "minimum_presence_seconds": 0,
                "absence_tolerance_seconds": 1,
                "cooldown_seconds": 5,
            })
            service = MonitoringService(
                FakeCameraManager(),
                zone_repository,
                event_repository,
                FakeSnapshotStore(),
                FakeDetector(),
            )

            service._process_camera(camera["id"])
            service._process_camera(camera["id"])

            events = event_repository.list(camera_id=camera["id"])
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["zone_type"], "WATER")
            self.assertEqual(events[0]["activity"], "NEAR_ZONE")

    def test_creates_event_when_detection_overlaps_zone_with_centroid_outside(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "monitoring.sqlite3")
            database.migrate()
            camera_repository = CameraRepository(database)
            zone_repository = ZoneRepository(database)
            event_repository = EventRepository(database)
            camera = camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
            zone_repository.create({
                "camera_id": camera["id"],
                "name": "Comida",
                "type": "FOOD",
                "polygon": ((0.55, 0.3), (0.8, 0.3), (0.8, 0.75), (0.55, 0.75)),
                "minimum_presence_seconds": 0,
                "absence_tolerance_seconds": 1,
                "cooldown_seconds": 5,
            })
            service = MonitoringService(
                FakeCameraManager(),
                zone_repository,
                event_repository,
                FakeSnapshotStore(),
                OverlappingDetector(),
            )

            service._process_camera(camera["id"])
            service._process_camera(camera["id"])

            events = event_repository.list(camera_id=camera["id"])
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["zone_type"], "FOOD")

    def test_ignores_minor_contact_with_zone_edge(self):
        zone = [(0.2, 0.2), (0.5, 0.2), (0.5, 0.5), (0.2, 0.5)]
        detection = Detection(0.49, 0.3, 0.8, 0.6, 0.9)

        self.assertFalse(MonitoringService._detection_in_zone(detection, zone))


if __name__ == "__main__":
    unittest.main()
