import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.domain.detection import Detection
from app.domain.zone_matching import assign_detections, detection_in_zone
from app.infra.database.database import Database
from app.infra.ai.pet_identifier import PetAnalysis, PetMatch
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.services.monitoring import MAX_CLIP_FRAMES, MAX_CLIP_SECONDS, MonitoringService
from app.services.monitoring import clips as clips_module


class FakeCameraManager:
    def latest_frame(self, camera_id):
        return np.zeros((240, 320, 3), dtype=np.uint8)

    def snapshot(self, camera_id):
        return b"jpeg"

    def connected_ids(self):
        return ["camera"]


class TogglingCameraManager(FakeCameraManager):
    def __init__(self):
        self.online = True

    def latest_frame(self, camera_id):
        return super().latest_frame(camera_id) if self.online else None

    def connected_ids(self):
        return ["camera"] if self.online else []


class HeavyClipStore:
    def __init__(self):
        self.saved = []

    def encode(self, frame):
        return b"x" * 1000

    def save(self, frames, captured_at, fps):
        self.saved.append((list(frames), captured_at, fps))
        return "clips/heavy.webm"


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


class FakePetImageStore:
    def extract_capture(self, frame, detection):
        return frame.copy()

    def save_capture_image(self, crop):
        return "pets/captures/test.jpg"

    def save_capture(self, frame, detection):
        return "pets/captures/test.jpg"


class FakePetIdentifier:
    def __init__(self, pet_id):
        self.pet_id = pet_id

    def analyze(self, capture_path, species):
        match = PetMatch(self.pet_id, 0.91)
        return PetAnalysis(match, "MATCHED", ({"pet_id": self.pet_id, "confidence": 0.91, "reference_count": 1},), 0.72, 0.08)

    def analyze_images(self, images, species):
        return self.analyze(None, species)

    def record_analysis(self, event_id, capture_path, species, analysis):
        return None


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

    def test_keeps_presence_state_isolated_between_cameras(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "monitoring.sqlite3")
            database.migrate()
            camera_repository = CameraRepository(database)
            zone_repository = ZoneRepository(database)
            event_repository = EventRepository(database)
            first_camera = camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
            second_camera = camera_repository.create({"name": "Cozinha", "ip": "192.168.1.11"})
            for camera in (first_camera, second_camera):
                zone_repository.create({
                    "camera_id": camera["id"],
                    "name": "Comida",
                    "type": "FOOD",
                    "polygon": ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)),
                    "minimum_presence_seconds": 2,
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

            with patch("app.services.monitoring.tracking.time.monotonic", side_effect=[10, 10, 12, 12]):
                service._process_camera(first_camera["id"])
                service._process_camera(second_camera["id"])
                service._process_camera(first_camera["id"])
                service._process_camera(second_camera["id"])

            self.assertEqual(len(event_repository.list(camera_id=first_camera["id"])), 1)
            self.assertEqual(len(event_repository.list(camera_id=second_camera["id"])), 1)
            self.assertEqual(set(service.tracker.runtimes), {first_camera["id"], second_camera["id"]})

    def test_assigns_automatically_identified_cat_to_new_event(self):
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
            database.execute(
                """INSERT INTO pets (id, name, species, description, created_at, updated_at)
                   VALUES ('mingau', 'Mingau', 'CAT', '', 'now', 'now')"""
            )
            service = MonitoringService(
                FakeCameraManager(), zone_repository, event_repository, FakeSnapshotStore(),
                FakeClipStore(), FakeDetector(), None, FakePetImageStore(), FakePetIdentifier("mingau"),
            )

            service._process_camera(camera["id"])
            service._process_camera(camera["id"])

            event = event_repository.list(camera_id=camera["id"])[0]
            self.assertEqual(event["pet_id"], "mingau")
            self.assertEqual(event["automatically_identified_pet_id"], "mingau")
            self.assertEqual(event["pet_identification_confidence"], 0.91)

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

        self.assertFalse(detection_in_zone(detection, zone))

    def test_assigns_detection_only_to_best_matching_zone(self):
        polygons = {
            "food": [(0.1, 0.2), (0.55, 0.2), (0.55, 0.6), (0.1, 0.6)],
            "water": [(0.45, 0.2), (0.8, 0.2), (0.8, 0.6), (0.45, 0.6)],
        }
        detection = Detection(0.4, 0.2, 0.78, 0.6, 0.9)

        assigned = assign_detections(polygons, [detection])

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

            with patch("app.services.monitoring.tracking.time.monotonic", side_effect=[10, 16, 17, 20, 22, 26]):
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
                "app.services.monitoring.tracking.time.monotonic",
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


class OfflineCameraAndMemoryTests(unittest.TestCase):
    def _setup(self, directory, clip_store, manager):
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
        service = MonitoringService(manager, zone_repository, event_repository, FakeSnapshotStore(), clip_store, FakeDetector())
        return camera, event_repository, service

    def test_open_event_finishes_when_camera_goes_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = TogglingCameraManager()
            camera, event_repository, service = self._setup(directory, FakeClipStore(), manager)
            with patch("app.services.monitoring.tracking.time.monotonic", side_effect=[10, 11, 13, 18]):
                service._process_camera(camera["id"])
                service._process_camera(camera["id"])
                self.assertIsNone(event_repository.list(camera_id=camera["id"])[0]["ended_at"])
                manager.online = False
                service._process_camera(camera["id"])
                service._process_camera(camera["id"])

            event = event_repository.list(camera_id=camera["id"])[0]
            self.assertIsNotNone(event["ended_at"])
            self.assertEqual(event["end_reason"], "CAT_LEFT_ZONE")
            self.assertEqual(service.feedback(camera["id"])["status"], "stopped")
            self.assertNotIn(camera["id"], service.tracker.runtimes)

    def test_clip_buffer_is_capped_by_closing_the_heaviest_clip_early(self):
        with tempfile.TemporaryDirectory() as directory:
            clip_store = HeavyClipStore()
            camera, event_repository, service = self._setup(directory, clip_store, FakeCameraManager())
            with patch.object(clips_module, "MAX_CLIP_BUFFER_BYTES", 2500), patch(
                "app.services.monitoring.tracking.time.monotonic", side_effect=[10, 11, 12, 13]
            ):
                for _ in range(4):
                    service._process_camera(camera["id"])

            event = event_repository.list(camera_id=camera["id"])[0]
            self.assertEqual(event["clip_path"], "clips/heavy.webm")
            self.assertEqual(len(clip_store.saved), 1)
            self.assertEqual(len(clip_store.saved[0][0]), 2)
            self.assertLessEqual(service.tracker.clip_bytes(), 2500)


if __name__ == "__main__":
    unittest.main()
