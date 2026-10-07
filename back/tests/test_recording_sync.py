import base64
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.infra.camera import onvif
from app.infra.camera.rtsp_replay import (
    ONVIF_REPLAY_EXTENSION,
    ReplayDownloader,
    ReplayError,
    _authorization,
    _parse_challenge,
    parse_rtp,
)
from app.infra.media.recording_reader import RecordingReader, index_path_for
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.monitoring_session_repository import MonitoringSessionRepository
from app.infra.repositories.recording_repository import RecordingRepository
from app.infra.security.credential_store import CredentialStore
from app.services.camera import CameraProfileService, CameraService
from app.services.recordings.camera_sync import CameraRecordingSync
from app.services.recordings.importer import RecordingImportService
from tests.test_monitoring import FakeCameraManager, build_repositories

START = datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)
NTP_EPOCH = datetime(1900, 1, 1, tzinfo=timezone.utc)


def ntp_extension(instant):
    delta = instant - NTP_EPOCH
    seconds = int(delta.total_seconds())
    fraction = int((delta.total_seconds() - seconds) * 2**32)
    return ONVIF_REPLAY_EXTENSION.to_bytes(2, "big") + (3).to_bytes(2, "big") + seconds.to_bytes(4, "big") + fraction.to_bytes(4, "big") + b"\x80\x00\x00\x00"


def rtp(payload, marker=False, payload_type=96, timestamp=None, seq=1):
    first = 0x80 | (0x10 if timestamp else 0)
    second = (0x80 if marker else 0) | payload_type
    header = bytes([first, second]) + seq.to_bytes(2, "big") + (seq * 3000).to_bytes(4, "big") + b"\x00\x00\x00\x01"
    extension = ntp_extension(timestamp) if timestamp else b""
    return header + extension + payload


def interleaved(channel, packet):
    return b"$" + bytes([channel]) + len(packet).to_bytes(2, "big") + packet


class FakeConnection:
    instances = []

    def __init__(self, uri, username, password, timeout):
        self.uri = uri
        self.requests = []
        self.closed = False
        self.packets = FakeConnection.script
        FakeConnection.instances.append(self)

    def request(self, method, url, headers=None):
        self.requests.append((method, url, headers or {}))
        if method == "DESCRIBE":
            sps = base64.b64encode(b"\x67\x42\x00\x1f").decode()
            pps = base64.b64encode(b"\x68\xce\x38\x80").decode()
            sdp = (
                "v=0\r\nm=video 0 RTP/AVP 96\r\na=rtpmap:96 H264/90000\r\n"
                f"a=fmtp:96 packetization-mode=1;sprop-parameter-sets={sps},{pps}\r\na=control:trackID=1\r\n"
            ).encode()
            return 200, {"content-type": "application/sdp"}, sdp
        if method == "SETUP":
            return 200, {"session": "ABC;timeout=60"}, b""
        return 200, {}, b""

    def interleaved(self):
        for channel, packet in self.packets:
            yield channel, packet

    def close(self):
        self.closed = True


class RtspReplayTests(unittest.TestCase):
    def test_parses_rtp_with_onvif_replay_extension(self):
        instant = START + timedelta(seconds=1.5)
        marker, payload_type, timestamp, payload = parse_rtp(rtp(b"\x65abc", marker=True, timestamp=instant))

        self.assertTrue(marker)
        self.assertEqual(payload_type, 96)
        self.assertAlmostEqual((timestamp - instant).total_seconds(), 0, places=3)
        self.assertEqual(payload, b"\x65abc")

    def test_downloads_h264_access_units_with_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            frame_one = START + timedelta(seconds=10)
            frame_two = START + timedelta(seconds=10.5)
            fu_start = bytes([0x7C, 0x85]) + b"AAAA"
            fu_end = bytes([0x7C, 0x45]) + b"BBBB"
            stap = bytes([0x78]) + (2).to_bytes(2, "big") + b"\x67\x01" + (2).to_bytes(2, "big") + b"\x68\x02"
            FakeConnection.script = [
                (1, b"rtcp"),
                (0, rtp(stap, timestamp=frame_one, seq=1)),
                (0, rtp(fu_start, seq=2)),
                (0, rtp(fu_end, marker=True, seq=3)),
                (0, rtp(b"\x65single", marker=True, timestamp=frame_two, seq=4)),
            ]
            FakeConnection.instances = []
            destination = Path(directory) / "cam" / "clip.h264"

            result = ReplayDownloader(connection_factory=FakeConnection).download(
                "rtsp://192.168.1.2/replay?token=r1", "admin", "secret", START, START + timedelta(minutes=1), destination
            )

            data = destination.read_bytes()
            self.assertEqual(result.frames, 2)
            self.assertEqual(result.codec, "h264")
            self.assertEqual(result.first_timestamp, frame_one)
            self.assertEqual(result.last_timestamp, frame_two)
            self.assertTrue(data.startswith(b"\x00\x00\x00\x01\x67\x42\x00\x1f\x00\x00\x00\x01\x68\xce\x38\x80"))
            self.assertIn(b"\x00\x00\x00\x01\x65AAAABBBB", data)
            self.assertIn(b"\x00\x00\x00\x01\x67\x01\x00\x00\x00\x01\x68\x02", data)
            index = json.loads(index_path_for(destination).read_text())
            self.assertEqual(len(index["timestamps"]), 2)
            connection = FakeConnection.instances[0]
            methods = [request[0] for request in connection.requests]
            self.assertEqual(methods, ["DESCRIBE", "SETUP", "PLAY", "TEARDOWN"])
            self.assertEqual(connection.requests[1][1], "rtsp://192.168.1.2/replay?token=r1/trackID=1")
            play_headers = connection.requests[2][2]
            self.assertEqual(play_headers["Range"], "clock=20261005T080000.000Z-20261005T080100.000Z")
            self.assertEqual(play_headers["Rate-Control"], "no")
            self.assertTrue(connection.closed)

    def test_empty_replay_raises_and_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as directory:
            FakeConnection.script = [(1, b"rtcp")]
            destination = Path(directory) / "clip.h264"

            with self.assertRaises(ReplayError):
                ReplayDownloader(connection_factory=FakeConnection).download(
                    "rtsp://192.168.1.2/replay", "", "", START, START + timedelta(minutes=1), destination
                )

            self.assertFalse(destination.exists())

    def test_digest_authorization_header(self):
        challenge = _parse_challenge('Digest realm="cam", nonce="abc", qop="auth"')
        header = _authorization(challenge, "DESCRIBE", "rtsp://c/x", "admin", "secret")

        self.assertTrue(header.startswith('Digest username="admin", realm="cam", nonce="abc", uri="rtsp://c/x"'))
        self.assertIn("qop=auth", header)
        basic = _authorization(_parse_challenge("Basic realm=cam"), "DESCRIBE", "rtsp://c/x", "admin", "secret")
        self.assertEqual(basic, "Basic " + base64.b64encode(b"admin:secret").decode())


class OnvifProfileGTests(unittest.TestCase):
    @patch("app.infra.camera.onvif._call")
    def test_recording_services_require_search_and_replay_on_same_host(self, call):
        call.return_value = ET.fromstring(
            "<Envelope><Service><Namespace>http://www.onvif.org/ver10/search/wsdl</Namespace>"
            "<XAddr>http://192.168.1.2/onvif/search</XAddr></Service>"
            "<Service><Namespace>http://www.onvif.org/ver10/replay/wsdl</Namespace>"
            "<XAddr>http://192.168.1.2/onvif/replay</XAddr></Service></Envelope>"
        )
        self.assertEqual(
            onvif.recording_services("192.168.1.2"),
            {"search": "http://192.168.1.2/onvif/search", "replay": "http://192.168.1.2/onvif/replay"},
        )
        call.return_value = ET.fromstring(
            "<Envelope><Service><Namespace>http://www.onvif.org/ver10/search/wsdl</Namespace>"
            "<XAddr>http://10.0.0.9/onvif/search</XAddr></Service></Envelope>"
        )
        self.assertEqual(onvif.recording_services("192.168.1.2"), {})

    @patch("app.infra.camera.onvif._call")
    def test_find_recordings_clamps_spans_to_requested_window(self, call):
        call.side_effect = [
            ET.fromstring("<Envelope><SearchToken>s1</SearchToken></Envelope>"),
            ET.fromstring(
                "<Envelope><RecordingInformation><RecordingToken>r1</RecordingToken>"
                "<EarliestRecording>2026-10-05T07:00:00Z</EarliestRecording>"
                "<LatestRecording>2026-10-05T08:30:00Z</LatestRecording></RecordingInformation>"
                "<RecordingInformation><RecordingToken>r2</RecordingToken>"
                "<EarliestRecording>2026-10-05T12:00:00Z</EarliestRecording>"
                "<LatestRecording>2026-10-05T13:00:00Z</LatestRecording></RecordingInformation></Envelope>"
            ),
        ]

        spans = onvif.find_recordings("http://192.168.1.2/onvif/search", START, START + timedelta(hours=1))

        self.assertEqual(len(spans), 1)
        self.assertEqual((spans[0].token, spans[0].start, spans[0].end), ("r1", START, START + timedelta(minutes=30)))

    @patch("app.infra.camera.onvif._call", side_effect=OSError("offline"))
    def test_find_recordings_reports_search_failure(self, call):
        with self.assertRaises(onvif.RecordingSearchError):
            onvif.find_recordings("http://192.168.1.2/onvif/search", START, START + timedelta(hours=1))

    @patch("app.infra.camera.onvif._call")
    def test_device_clock_offset_reads_utc_time(self, call):
        call.return_value = ET.fromstring(
            "<Envelope><UTCDateTime><Time><Hour>8</Hour><Minute>5</Minute><Second>0</Second></Time>"
            "<Date><Year>2026</Year><Month>10</Month><Day>5</Day></Date></UTCDateTime></Envelope>"
        )
        with patch("app.infra.camera.onvif.datetime") as frozen:
            frozen.now.return_value = START
            frozen.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            offset = onvif.device_clock_offset("192.168.1.2")

        self.assertEqual(offset, 300.0)

    @patch("app.infra.camera.onvif._call")
    def test_replay_uri_rejects_other_hosts(self, call):
        call.return_value = ET.fromstring("<Envelope><Uri>rtsp://attacker.example/replay</Uri></Envelope>")
        self.assertIsNone(onvif.replay_uri("http://192.168.1.2/onvif/replay", "r1", "192.168.1.2"))
        call.return_value = ET.fromstring("<Envelope><Uri>rtsp://192.168.1.2:554/replay?token=r1</Uri></Envelope>")
        self.assertEqual(onvif.replay_uri("http://192.168.1.2/onvif/replay", "r1", "192.168.1.2"), "rtsp://192.168.1.2:554/replay?token=r1")


class CredentialStoreTests(unittest.TestCase):
    def test_round_trip_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(Path(directory))
            store.save("cam", "admin", "s3nh@ çom acento")

            self.assertEqual(store.get("cam"), ("admin", "s3nh@ çom acento"))
            self.assertNotIn(b"s3nh@", store.path.read_bytes())
            store.delete("cam")
            self.assertIsNone(store.get("cam"))


class RecordingReaderIndexTests(unittest.TestCase):
    def test_offsets_follow_index_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            from app.infra.media.clip_store import ClipStore
            import numpy as np

            data_dir = Path(directory)
            store = ClipStore(data_dir, data_dir / "clips")
            encoded = store.encode(np.zeros((120, 160, 3), dtype=np.uint8))
            relative = store.save([encoded] * 4, START, fps=3.0)
            path = data_dir / relative
            stamps = [START.timestamp() + offset for offset in (0.0, 0.5, 7.0, 7.5)]
            index_path_for(path).write_text(json.dumps({"codec": "vp8", "timestamps": stamps}))
            reader = RecordingReader(path)

            info = reader.probe()
            offsets = [offset for offset, _ in reader.frames(sample_fps=100)]

            self.assertEqual(info.frame_count, 4)
            self.assertAlmostEqual(info.duration_seconds, 7.5 + 7.5 / 3)
            self.assertEqual(offsets, [0.0, 0.5, 7.0, 7.5])


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, uri, username, password, start, end, destination, on_progress=None):
        self.calls.append((uri, username, password, start, end, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"\x00\x00\x00\x01\x67" + start.isoformat().encode())
        stamps = [start.timestamp() + offset for offset in range(int((end - start).total_seconds()))]
        index_path_for(destination).write_text(json.dumps({"codec": "h264", "timestamps": stamps}))
        from app.infra.camera.rtsp_replay import ReplayResult
        return ReplayResult(destination, "h264", len(stamps), start, end - timedelta(seconds=1))


class ProbeReader:
    def __init__(self, path):
        self.path = Path(path)

    def probe(self):
        from app.infra.media.recording_reader import RecordingInfo
        stamps = json.loads(index_path_for(self.path).read_text())["timestamps"]
        return RecordingInfo(len(stamps), 1.0, len(stamps), 160, 120)


class CameraSyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.directory.name)
        self.database, self.camera_repository, self.zone_repository, self.event_repository = build_repositories(self.directory.name)
        self.sessions = MonitoringSessionRepository(self.database)
        self.recordings = RecordingRepository(self.database)
        self.camera = self.camera_repository.create({"name": "Sala", "ip": "192.168.1.2"})
        self.camera_repository.update_recording_profile(self.camera["id"], "ONVIF_REPLAY", 120.0)
        self.credentials = CredentialStore(self.data_dir)
        self.credentials.save(self.camera["id"], "admin", "secret")
        self.profile = CameraProfileService(self.camera_repository, self.credentials)
        from app.infra.media.media_cleanup import MediaCleanup
        from app.services.event.purge import EventPurgeService
        purge = EventPurgeService(self.event_repository, self.recordings, MediaCleanup(self.data_dir))
        camera_service = CameraService(self.camera_repository, FakeCameraManager(), purge, self.profile)
        self.importer = RecordingImportService(self.recordings, camera_service, purge, reader_factory=ProbeReader)
        self.downloader = FakeDownloader()
        self.spans = [onvif.RecordingSpan("r1", START + timedelta(seconds=120), START + timedelta(hours=3, seconds=120))]
        self.sync = CameraRecordingSync(
            self.camera_repository, self.sessions, self.recordings, self.profile, self.importer,
            self.data_dir / "recordings", downloader=self.downloader,
            find_recordings=lambda *args: self.spans,
            recording_services=lambda *args: {"search": "http://192.168.1.2/s", "replay": "http://192.168.1.2/r"},
            replay_uri=lambda *args: "rtsp://192.168.1.2/replay?token=r1",
            now=lambda: START + timedelta(hours=3),
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_downloads_uncovered_chunks_with_clock_offset_applied(self):
        session = self.sessions.open(self.camera["id"], START + timedelta(hours=1))
        self.sessions.extend(session, START + timedelta(hours=1, minutes=30))

        result = self.sync.sync(self.camera["id"], since=START, until=START + timedelta(hours=3))

        requested = [(call[3], call[4]) for call in self.downloader.calls]
        self.assertEqual(requested, [
            (START + timedelta(seconds=120), START + timedelta(hours=1, seconds=120)),
            (START + timedelta(hours=1, minutes=30, seconds=120), START + timedelta(hours=2, minutes=30, seconds=120)),
            (START + timedelta(hours=2, minutes=30, seconds=120), START + timedelta(hours=3, seconds=120)),
        ])
        self.assertEqual(self.downloader.calls[0][1:3], ("admin", "secret"))
        self.assertEqual(len(result.downloaded), 3)
        self.assertEqual(result.downloaded[0]["started_at"], START.isoformat())
        self.assertEqual(result.downloaded[0]["origin"], "CAMERA")
        self.assertEqual(result.skipped_seconds, 1800.0)
        self.assertEqual(self.camera_repository.get(self.camera["id"])["last_synced_at"], (START + timedelta(hours=3)).isoformat())

    def test_second_sync_skips_already_registered_periods(self):
        self.sync.sync(self.camera["id"], since=START, until=START + timedelta(hours=3))
        calls_before = len(self.downloader.calls)

        result = self.sync.sync(self.camera["id"], since=START, until=START + timedelta(hours=3))

        self.assertEqual(len(self.downloader.calls), calls_before)
        self.assertEqual(result.downloaded, [])

    def test_sync_refuses_camera_without_replay_support(self):
        self.camera_repository.update_recording_profile(self.camera["id"], "NONE", None)
        from app.domain.errors import OperationFailedError

        with self.assertRaises(OperationFailedError):
            self.sync.sync(self.camera["id"])

    def test_sync_does_not_advance_checkpoint_when_a_download_fails(self):
        from app.infra.camera.rtsp_replay import ReplayError

        def fail(*args, **kwargs):
            raise ReplayError("offline")

        self.downloader.download = fail

        result = self.sync.sync(self.camera["id"], since=START, until=START + timedelta(hours=3))

        self.assertTrue(result.errors)
        self.assertIsNone(self.camera_repository.get(self.camera["id"])["last_synced_at"])

    def test_sync_reports_recording_search_failure_as_domain_error(self):
        from app.domain.errors import OperationFailedError

        def fail(*args, **kwargs):
            raise onvif.RecordingSearchError("Não foi possível consultar as gravações da câmera.")

        self.sync._find_recordings = fail

        with self.assertRaises(OperationFailedError):
            self.sync.sync(self.camera["id"], since=START, until=START + timedelta(hours=3))
        self.assertIsNone(self.camera_repository.get(self.camera["id"])["last_synced_at"])


class CameraProfileTests(unittest.TestCase):
    def test_connect_remembers_credentials_and_probes_support(self):
        with tempfile.TemporaryDirectory() as directory:
            database, camera_repository, _, _ = build_repositories(directory)
            camera = camera_repository.create({"name": "Sala", "ip": "192.168.1.2"})
            credentials = CredentialStore(Path(directory))
            profile = CameraProfileService(
                camera_repository, credentials,
                recording_services=lambda ip, port, user, pw: {"search": "s", "replay": "r"} if pw == "secret" else {},
                clock_offset=lambda ip, port, user, pw: 42.0,
            )
            manager = FakeCameraManager()
            manager.status = lambda camera_id: {"connected": False}
            service = CameraService(camera_repository, manager, None, profile)
            from app.services.camera import CameraCredentialsCommand

            self.assertFalse(service.list()[0]["credentials_saved"])

            with patch("app.services.camera.service.resolve_connection_urls", return_value=["rtsp://x"]), patch.object(
                FakeCameraManager, "connect", create=True, return_value=None
            ), patch.object(FakeCameraManager, "status", create=True, return_value={"connected": True}):
                service.connect(camera["id"], CameraCredentialsCommand("admin", "secret", None))

            stored = camera_repository.get(camera["id"])
            self.assertEqual(stored["recording_support"], "ONVIF_REPLAY")
            self.assertEqual(stored["clock_offset_seconds"], 42.0)
            self.assertEqual(credentials.get(camera["id"]), ("admin", "secret"))
            self.assertTrue(service.list()[0]["credentials_saved"])


if __name__ == "__main__":
    unittest.main()
