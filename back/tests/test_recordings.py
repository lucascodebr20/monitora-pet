import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from app.domain.detection import Detection
from app.domain.intervals import contains, subtract_intervals
from app.infra.media.media_cleanup import MediaCleanup
from app.infra.media.recording_reader import RecordingInfo, RecordingReader, RecordingUnreadableError
from app.infra.media.clip_store import ClipStore
from app.infra.repositories.monitoring_session_repository import MonitoringSessionRepository
from app.infra.repositories.recording_repository import RecordingRepository
from app.services.event.purge import EventPurgeService
from app.services.monitoring import MonitoringService
from app.services.recordings import RecordingAnalyzer, RecordingImportService
from tests.test_monitoring import (
    FakeCameraManager,
    FakeClipStore,
    FakeSnapshotStore,
    FailingDetector,
    SequenceClock,
    TogglingCameraManager,
    build_repositories,
    square_zone,
)

START = datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)


def at(seconds):
    return (START + timedelta(seconds=seconds)).isoformat()


def frame_with_pet(present):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    if present:
        frame[0, 0, 0] = 255
    return frame


class MarkerDetector:
    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return [Detection(0.4, 0.4, 0.6, 0.6, 0.9)] if frame[0, 0, 0] else []


class ScriptedReader:
    scenes = {}

    def __init__(self, path):
        self.path = Path(path)

    def frames(self, sample_fps):
        scene = self.scenes[self.path.name]
        if scene == "unreadable":
            raise RecordingUnreadableError("codec não suportado")
        duration, present = scene
        step = 1 / sample_fps
        offset = 0.0
        while offset < duration:
            yield offset, frame_with_pet(present(offset))
            offset += step

    def probe(self):
        duration, _ = self.scenes[self.path.name]
        return RecordingInfo(duration, 2.0, int(duration * 2), 160, 120)


class AlwaysMoving:
    def changed(self, frame):
        return True


class StaticAfterFirst:
    def __init__(self):
        self.seen = False

    def changed(self, frame):
        changed = not self.seen
        self.seen = True
        return changed


class RecordingAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database, self.camera_repository, self.zone_repository, self.event_repository = build_repositories(self.directory.name)
        self.sessions = MonitoringSessionRepository(self.database)
        self.recordings = RecordingRepository(self.database)
        self.camera = self.camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
        self.zone_repository.create(square_zone(self.camera["id"], "Comida", "FOOD", 1, cooldown=3, tolerance=1))
        self.detector = MarkerDetector()
        self.snapshot_store = FakeSnapshotStore()
        self.clip_store = FakeClipStore()
        self.purge = EventPurgeService(self.event_repository, self.recordings, MediaCleanup(Path(self.directory.name)))
        ScriptedReader.scenes = {}

    def tearDown(self):
        self.directory.cleanup()

    def _analyzer(self, gate_factory=AlwaysMoving):
        return RecordingAnalyzer(
            self.detector, self.zone_repository, self.event_repository, self.snapshot_store, self.clip_store,
            self.sessions, self.recordings, self.purge, reader_factory=ScriptedReader, motion_gate_factory=gate_factory,
        )

    def _recording(self, name, start_seconds, duration, present):
        ScriptedReader.scenes[name] = (duration, present)
        return self.recordings.create({
            "camera_id": self.camera["id"], "origin": "FOLDER", "path": f"C:/gravacoes/{name}",
            "fingerprint": name, "size_bytes": 10, "started_at": at(start_seconds), "ended_at": at(start_seconds + duration),
        })

    def test_creates_event_with_recording_timestamps(self):
        recording = self._recording("a.mp4", 0, 20, lambda offset: 2 <= offset <= 8)

        result = self._analyzer().analyze_camera(self.camera["id"], [recording])

        events = self.event_repository.list(camera_id=self.camera["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "RECORDING")
        self.assertEqual(events[0]["recording_id"], recording["id"])
        self.assertEqual(events[0]["started_at"], at(2))
        self.assertEqual(events[0]["ended_at"], at(8))
        self.assertEqual(events[0]["duration_seconds"], 6)
        self.assertEqual(events[0]["end_reason"], "CAT_LEFT_ZONE")
        self.assertEqual(events[0]["clip_path"], "clips/test.webm")
        self.assertEqual(self.snapshot_store.saved[0][0], b"frame-jpeg")
        self.assertEqual(self.recordings.get(recording["id"])["status"], "DONE")
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.frames_analyzed, 40)

    def test_event_open_at_end_of_last_recording_is_finished(self):
        recording = self._recording("a.mp4", 0, 10, lambda offset: offset >= 4)

        self._analyzer().analyze_camera(self.camera["id"], [recording])

        event = self.event_repository.list(camera_id=self.camera["id"])[0]
        self.assertEqual(event["started_at"], at(4))
        self.assertEqual(event["ended_at"], at(9.5))

    def test_skips_recording_fully_covered_by_live_monitoring(self):
        recording = self._recording("a.mp4", 0, 20, lambda offset: True)
        session = self.sessions.open(self.camera["id"], START - timedelta(minutes=1))
        self.sessions.extend(session, START + timedelta(minutes=1))

        result = self._analyzer().analyze_camera(self.camera["id"], [recording])

        self.assertEqual(self.event_repository.list(camera_id=self.camera["id"]), [])
        self.assertEqual(self.recordings.get(recording["id"])["status"], "SKIPPED")
        self.assertEqual(result.skipped, 1)
        self.assertEqual(self.detector.calls, 0)

    def test_analyzes_only_periods_not_covered_by_live_monitoring(self):
        recording = self._recording("a.mp4", 0, 20, lambda offset: True)
        session = self.sessions.open(self.camera["id"], START - timedelta(minutes=1))
        self.sessions.extend(session, START + timedelta(seconds=10))

        self._analyzer().analyze_camera(self.camera["id"], [recording])

        events = self.event_repository.list(camera_id=self.camera["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["started_at"], at(10))
        self.assertEqual(events[0]["ended_at"], at(19.5))

    def test_gap_between_recordings_finishes_event(self):
        first = self._recording("a.mp4", 0, 10, lambda offset: True)
        second = self._recording("b.mp4", 60, 10, lambda offset: offset < 5)

        self._analyzer().analyze_camera(self.camera["id"], [second, first])

        events = sorted(self.event_repository.list(camera_id=self.camera["id"]), key=lambda event: event["started_at"])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["recording_id"], first["id"])
        self.assertEqual((events[0]["started_at"], events[0]["ended_at"]), (at(0), at(9.5)))
        self.assertEqual(events[1]["recording_id"], second["id"])
        self.assertEqual((events[1]["started_at"], events[1]["ended_at"]), (at(60), at(64.5)))

    def test_contiguous_recordings_keep_single_event(self):
        first = self._recording("a.mp4", 0, 10, lambda offset: True)
        self._recording("b.mp4", 10, 10, lambda offset: offset < 5)

        self._analyzer().analyze_camera(self.camera["id"], [first, self.recordings.list(self.camera["id"])[1]])

        events = self.event_repository.list(camera_id=self.camera["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]["started_at"], events[0]["ended_at"]), (at(0), at(14.5)))
        self.assertEqual(events[0]["recording_id"], first["id"])

    def test_unreadable_recording_is_marked_failed_without_stopping_batch(self):
        ScriptedReader.scenes["bad.mp4"] = "unreadable"
        bad = self.recordings.create({
            "camera_id": self.camera["id"], "origin": "FOLDER", "path": "C:/gravacoes/bad.mp4",
            "fingerprint": "bad", "size_bytes": 10, "started_at": at(0), "ended_at": at(10),
        })
        good = self._recording("good.mp4", 20, 10, lambda offset: offset < 5)

        result = self._analyzer().analyze_camera(self.camera["id"], [bad, good])

        self.assertEqual(self.recordings.get(bad["id"])["status"], "FAILED")
        self.assertIn("codec", self.recordings.get(bad["id"])["error"])
        self.assertEqual(self.recordings.get(good["id"])["status"], "DONE")
        self.assertEqual((result.failed, result.processed), (1, 1))
        self.assertEqual(len(self.event_repository.list(camera_id=self.camera["id"])), 1)

    def test_reuses_detections_while_scene_is_static(self):
        recording = self._recording("a.mp4", 0, 10, lambda offset: True)

        result = self._analyzer(StaticAfterFirst).analyze_camera(self.camera["id"], [recording])

        self.assertEqual(self.detector.calls, 1)
        self.assertEqual(result.detections_run, 1)
        self.assertEqual(result.frames_analyzed, 20)
        self.assertEqual(len(self.event_repository.list(camera_id=self.camera["id"])), 1)

    def test_stop_request_leaves_recording_pending(self):
        recording = self._recording("a.mp4", 0, 10, lambda offset: True)
        ticks = iter(range(100))

        result = self._analyzer().analyze_camera(self.camera["id"], [recording], should_stop=lambda: next(ticks) > 5)

        self.assertTrue(result.interrupted)
        self.assertEqual(self.recordings.get(recording["id"])["status"], "PENDING")

    def test_retry_after_stop_replaces_partial_events(self):
        recording = self._recording("a.mp4", 0, 10, lambda offset: True)
        ticks = iter(range(100))

        self._analyzer().analyze_camera(
            self.camera["id"], [recording], should_stop=lambda: next(ticks) > 5
        )
        self.assertEqual(self.recordings.get(recording["id"])["processed_seconds"], 0)
        self._analyzer().analyze_camera(self.camera["id"], [self.recordings.get(recording["id"])])

        events = self.event_repository.list(camera_id=self.camera["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]["started_at"], events[0]["ended_at"]), (at(0), at(9.5)))

    def test_live_restart_does_not_close_recording_events(self):
        self.event_repository.create_detected_event(
            self.camera["id"], self.zone_repository.list()[0]["id"], at(0), at(1), 0.9, None, "CAT", None,
            source="RECORDING", recording_id=None,
        )
        self.event_repository.create_detected_event(
            self.camera["id"], self.zone_repository.list()[0]["id"], at(0), at(1), 0.9, None, "CAT", None,
        )

        self.event_repository.finish_open_events(at(100))

        events = {event["source"]: event for event in self.event_repository.list(camera_id=self.camera["id"])}
        self.assertIsNone(events["RECORDING"]["ended_at"])
        self.assertEqual(events["LIVE"]["end_reason"], "APPLICATION_RESTART")


class RecordingImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.directory.name)
        self.database, self.camera_repository, self.zone_repository, self.event_repository = build_repositories(self.directory.name)
        self.recordings = RecordingRepository(self.database)
        self.camera = self.camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
        self.zone = self.zone_repository.create(square_zone(self.camera["id"], "Comida", "FOOD", 1))
        ScriptedReader.scenes = {"video.mp4": (30, lambda offset: False)}
        self.file = self.data_dir / "video.mp4"
        self.file.write_bytes(b"\x00" * 4096)
        from app.services.camera import CameraService
        purge = EventPurgeService(self.event_repository, self.recordings, MediaCleanup(self.data_dir))
        self.service = RecordingImportService(
            self.recordings, CameraService(self.camera_repository, FakeCameraManager(), purge), purge, reader_factory=ScriptedReader
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_register_is_idempotent_for_same_file(self):
        first = self.service.register(self.camera["id"], self.file, START)
        second = self.service.register(self.camera["id"], self.file, START + timedelta(hours=1))

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["ended_at"], at(30))
        self.assertEqual(first["status"], "PENDING")
        self.assertEqual(len(self.recordings.list(self.camera["id"])), 1)

    def test_reprocess_removes_events_and_media_then_resets_status(self):
        recording = self.service.register(self.camera["id"], self.file, START)
        snapshot = self.data_dir / "snapshots" / "x.jpg"
        snapshot.parent.mkdir()
        snapshot.write_bytes(b"jpg")
        self.event_repository.create_detected_event(
            self.camera["id"], self.zone["id"], at(0), at(1), 0.9, "snapshots/x.jpg", "CAT", None,
            source="RECORDING", recording_id=recording["id"],
        )
        self.recordings.set_status(recording["id"], "DONE")

        reset = self.service.reprocess(recording["id"])

        self.assertEqual(reset["status"], "PENDING")
        self.assertEqual(self.event_repository.list(camera_id=self.camera["id"]), [])
        self.assertFalse(snapshot.exists())

    def test_reprocess_requires_original_file(self):
        recording = self.service.register(self.camera["id"], self.file, START)
        self.file.unlink()

        from app.domain.errors import OperationFailedError
        with self.assertRaises(OperationFailedError):
            self.service.reprocess(recording["id"])


class CoverageAndPurgeTests(unittest.TestCase):
    def test_failed_live_analysis_is_not_recorded_as_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            database, camera_repository, zone_repository, event_repository = build_repositories(directory)
            sessions = MonitoringSessionRepository(database)
            camera = camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
            service = MonitoringService(
                FakeCameraManager(), zone_repository, event_repository, FakeSnapshotStore(), FakeClipStore(),
                FailingDetector(), clock=SequenceClock([10]), session_repository=sessions,
            )

            service._process_camera(camera["id"])

            epoch = SequenceClock([0]).now().utc
            self.assertEqual(sessions.covered_intervals(camera["id"], epoch, epoch + timedelta(hours=1)), [])

    def test_live_monitoring_records_coverage_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            database, camera_repository, zone_repository, event_repository = build_repositories(directory)
            sessions = MonitoringSessionRepository(database)
            camera = camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
            zone_repository.create(square_zone(camera["id"], "Comida", "FOOD", 0))
            manager = TogglingCameraManager()
            service = MonitoringService(
                manager, zone_repository, event_repository, FakeSnapshotStore(), FakeClipStore(), MarkerDetector(),
                clock=SequenceClock([10, 20, 40, 41]), session_repository=sessions,
            )

            service._process_camera(camera["id"])
            service._process_camera(camera["id"])
            service._process_camera(camera["id"])
            manager.online = False
            service._process_camera(camera["id"])

            epoch = SequenceClock([0]).now().utc
            intervals = sessions.covered_intervals(camera["id"], epoch, epoch + timedelta(hours=1))
            self.assertEqual(intervals, [(epoch + timedelta(seconds=10), epoch + timedelta(seconds=40))])

    def test_deleting_zone_removes_events_and_unreferenced_media(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            database, camera_repository, zone_repository, event_repository = build_repositories(directory)
            camera = camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
            zone = zone_repository.create(square_zone(camera["id"], "Comida", "FOOD", 0))
            for name in ("snapshots/a.jpg", "pets/captures/b.jpg", "pets/captures/c.jpg"):
                (data_dir / name).parent.mkdir(parents=True, exist_ok=True)
                (data_dir / name).write_bytes(b"x")
            event_id = event_repository.create_detected_event(
                camera["id"], zone["id"], at(0), at(1), 0.9, "snapshots/a.jpg", "CAT", "pets/captures/b.jpg"
            )
            event_repository.create_detected_event(
                camera["id"], zone["id"], at(5), at(6), 0.9, None, "CAT", "pets/captures/c.jpg"
            )
            database.execute(
                """INSERT INTO pets (id, name, species, description, created_at, updated_at)
                   VALUES ('mingau', 'Mingau', 'CAT', '', 'now', 'now')"""
            )
            database.execute(
                """INSERT INTO pet_reference_images (id, pet_id, event_id, image_path, created_at)
                   VALUES ('ref', 'mingau', ?, 'pets/captures/b.jpg', 'now')""",
                (event_id,),
            )
            from app.services.camera import CameraService
            from app.services.zone import ZoneService
            purge = EventPurgeService(event_repository, RecordingRepository(database), MediaCleanup(data_dir))
            zone_service = ZoneService(zone_repository, CameraService(camera_repository, FakeCameraManager(), purge), purge)

            zone_service.delete(zone["id"])

            self.assertEqual(zone_repository.list(), [])
            self.assertEqual(event_repository.list(camera_id=camera["id"]), [])
            self.assertFalse((data_dir / "snapshots/a.jpg").exists())
            self.assertFalse((data_dir / "pets/captures/c.jpg").exists())
            self.assertTrue((data_dir / "pets/captures/b.jpg").exists())
            self.assertEqual(database.one("SELECT event_id FROM pet_reference_images WHERE id = 'ref'")["event_id"], None)


class IntervalTests(unittest.TestCase):
    def test_subtracts_covered_intervals(self):
        start, end = START, START + timedelta(seconds=100)
        covered = [
            (START - timedelta(seconds=10), START + timedelta(seconds=10)),
            (START + timedelta(seconds=40), START + timedelta(seconds=50)),
            (START + timedelta(seconds=45), START + timedelta(seconds=60)),
        ]

        windows = subtract_intervals(start, end, covered)

        self.assertEqual(windows, [
            (START + timedelta(seconds=10), START + timedelta(seconds=40)),
            (START + timedelta(seconds=60), end),
        ])
        self.assertTrue(contains(windows, START + timedelta(seconds=10)))
        self.assertFalse(contains(windows, START + timedelta(seconds=40)))
        self.assertEqual(subtract_intervals(start, end, [(start, end)]), [])
        self.assertEqual(subtract_intervals(start, end, []), [(start, end)])


class RecordingReaderTests(unittest.TestCase):
    def test_probes_and_samples_real_file(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            store = ClipStore(data_dir, data_dir / "clips")
            encoded = store.encode(np.zeros((120, 160, 3), dtype=np.uint8))
            relative = store.save([encoded] * 9, START, fps=3.0)
            reader = RecordingReader(data_dir / relative)

            info = reader.probe()
            samples = list(reader.frames(sample_fps=1.0))

            self.assertEqual(info.frame_count, 9)
            self.assertAlmostEqual(info.duration_seconds, 3.0)
            self.assertEqual((info.width, info.height), (160, 120))
            self.assertEqual([offset for offset, _ in samples], [0.0, 1.0, 2.0])
            self.assertEqual(samples[0][1].shape, (120, 160, 3))

    def test_missing_file_is_unreadable(self):
        with self.assertRaises(RecordingUnreadableError):
            RecordingReader(Path("C:/nao/existe.mp4")).probe()


if __name__ == "__main__":
    unittest.main()
