import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.domain.detection import Detection
from app.infra.database.database import Database
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.services.monitoring_service import MAX_CLIP_FRAMES, MAX_CLIP_SECONDS, MonitoringService


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


class MutableDetector:
    def __init__(self, detection):
        self.detection = detection

    def detect(self, frame):
        return [self.detection] if self.detection else []


class FakeSnapshotStore:
    def save(self, content, captured_at):
        return "snapshots/test.jpg"


class FakeClipStore:
    def __init__(self):
        self.saved = []

    def encode(self, frame):
        return b"frame"

    def save(self, frames, captured_at, fps):
        self.saved.append((list(frames), captured_at, fps))
        return "clips/test.webm"


class MonitoringTests(unittest.TestCase):
    def test_clip_limit_is_five_minutes(self):
        self.assertEqual(MAX_CLIP_SECONDS, 300)
        self.assertEqual(MAX_CLIP_FRAMES, 900)

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
                FakeClipStore(),
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
                FakeClipStore(),
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

    def test_assigns_detection_only_to_best_matching_zone(self):
        polygons = {
            "food": [(0.1, 0.2), (0.55, 0.2), (0.55, 0.6), (0.1, 0.6)],
            "water": [(0.45, 0.2), (0.8, 0.2), (0.8, 0.6), (0.45, 0.6)],
        }
        detection = Detection(0.4, 0.2, 0.78, 0.6, 0.9)

        assigned = MonitoringService._assign_detections(polygons, [detection])

        self.assertEqual(assigned["food"], [])
        self.assertEqual(assigned["water"], [detection])

    def test_switches_from_food_to_water_without_extending_food_event(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "monitoring.sqlite3")
            database.migrate()
            camera_repository = CameraRepository(database)
            zone_repository = ZoneRepository(database)
            event_repository = EventRepository(database)
            camera = camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
            shared = {
                "camera_id": camera["id"],
                "absence_tolerance_seconds": 1,
                "cooldown_seconds": 5,
            }
            zone_repository.create({
                **shared,
                "name": "Comida",
                "type": "FOOD",
                "polygon": ((0.1, 0.2), (0.55, 0.2), (0.55, 0.6), (0.1, 0.6)),
                "minimum_presence_seconds": 5,
            })
            zone_repository.create({
                **shared,
                "name": "Água",
                "type": "WATER",
                "polygon": ((0.45, 0.2), (0.8, 0.2), (0.8, 0.6), (0.45, 0.6)),
                "minimum_presence_seconds": 3,
            })
            detector = MutableDetector(Detection(0.1, 0.2, 0.5, 0.6, 0.9))
            service = MonitoringService(
                FakeCameraManager(),
                zone_repository,
                event_repository,
                FakeSnapshotStore(),
                FakeClipStore(),
                detector,
            )

            with patch("app.services.monitoring_service.time.monotonic", side_effect=[10, 16, 17, 20, 22, 26]):
                service._process_camera(camera["id"])
                service._process_camera(camera["id"])
                detector.detection = Detection(0.4, 0.2, 0.78, 0.6, 0.9)
                service._process_camera(camera["id"])
                service._process_camera(camera["id"])
                detector.detection = None
                service._process_camera(camera["id"])
                service._process_camera(camera["id"])

            events = {event["zone_type"]: event for event in event_repository.list(camera_id=camera["id"])}
            self.assertEqual(events["FOOD"]["duration_seconds"], 6)
            self.assertEqual(events["WATER"]["duration_seconds"], 3)

    def test_attaches_clip_when_event_finishes(self):
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
                "polygon": ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)),
                "minimum_presence_seconds": 0,
                "absence_tolerance_seconds": 1,
                "cooldown_seconds": 5,
            })
            detector = FakeDetector()
            clip_store = FakeClipStore()
            service = MonitoringService(
                FakeCameraManager(),
                zone_repository,
                event_repository,
                FakeSnapshotStore(),
                clip_store,
                detector,
            )

            with patch(
                "app.services.monitoring_service.time.monotonic",
                side_effect=[10, 11, 13, 18],
            ):
                service._process_camera(camera["id"])
                service._process_camera(camera["id"])
                self.assertEqual(event_repository.list(pending_review=True), [])
                detector.detect = lambda frame: []
                service._process_camera(camera["id"])
                service._process_camera(camera["id"])

            event = event_repository.list(camera_id=camera["id"])[0]
            self.assertEqual(event["clip_path"], "clips/test.webm")
            self.assertEqual(len(clip_store.saved[0][0]), 2)
            self.assertEqual(len(event_repository.list(pending_review=True)), 1)


if __name__ == "__main__":
    unittest.main()
