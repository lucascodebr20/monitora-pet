import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.infra.media.clip_store import ClipStore


class ClipStoreTests(unittest.TestCase):
    def test_writes_browser_compatible_webm(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            store = ClipStore(data_dir, data_dir / "clips")
            frame = np.zeros((120, 160, 3), dtype=np.uint8)
            encoded = store.encode(frame)

            relative_path = store.save([encoded, encoded, encoded], datetime.now(timezone.utc))

            self.assertIsNotNone(relative_path)
            self.assertTrue((data_dir / relative_path).is_file())


if __name__ == "__main__":
    unittest.main()
