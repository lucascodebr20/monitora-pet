import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.domain.detection import Detection
from app.infra.media.pet_image_store import PetImageStore
from app.infra.media.snapshot_store import SnapshotStore


class MediaStoreTests(unittest.TestCase):
    def test_pet_capture_folder_follows_capture_time(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            store = PetImageStore(data_dir, data_dir / "pets")
            frame = np.zeros((120, 160, 3), dtype=np.uint8)
            captured_at = datetime(2026, 3, 9, 23, 30, tzinfo=timezone.utc)

            path = store.save_capture(frame, Detection(0.2, 0.2, 0.8, 0.8, 0.9), captured_at)

            self.assertTrue(path.startswith("pets/captures/2026/03/09/"))
            self.assertTrue((data_dir / path).is_file())

    def test_snapshot_store_encodes_frame_as_jpeg(self):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)

        encoded = SnapshotStore.encode(frame)

        self.assertIsNotNone(encoded)
        self.assertEqual(encoded[:3], b"\xff\xd8\xff")


if __name__ == "__main__":
    unittest.main()
