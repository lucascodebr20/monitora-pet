import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging_setup import reset_logging
from app.main import create_app


def photo_data_url() -> str:
    image = np.full((64, 64, 3), 120, dtype=np.uint8)
    encoded, jpeg = cv2.imencode(".jpg", image)
    assert encoded
    return "data:image/jpeg;base64," + base64.b64encode(jpeg.tobytes()).decode()


SQUARE = [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.settings = Settings(data_dir=root / "data", frontend_dist=root / "dist")
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        reset_logging()
        self.temp.cleanup()

    def test_health_and_dashboard_without_model(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["inference"]["status"], "model_missing")
        self.assertEqual(health.json()["cameras"], {"registered": 0, "connected": 0})
        dashboard = self.client.get("/api/dashboard").json()
        self.assertEqual(dashboard["events_today"], 0)
        self.assertEqual(dashboard["pending_reviews"], 0)
        self.assertTrue((self.settings.log_dir / "vigiapet.log").exists())

    def test_domain_errors_become_http_statuses(self):
        self.assertEqual(self.client.get("/api/pets/nao-existe/photo").status_code, 404)
        self.assertEqual(self.client.get("/api/monitoring/nao-existe").status_code, 404)
        no_photo = self.client.post("/api/pets", json={"name": "Mingau", "species": "CAT"})
        self.assertEqual(no_photo.status_code, 422)
        self.assertIn("foto", no_photo.json()["detail"])
        bad_photo = self.client.post("/api/pets", json={"name": "Mingau", "species": "CAT", "photo_data": "data:image/png;base64,xx"})
        self.assertEqual(bad_photo.status_code, 422)
        orphan_zone = self.client.post("/api/zones", json={"camera_id": "x", "name": "Água", "type": "WATER", "polygon": SQUARE})
        self.assertEqual(orphan_zone.status_code, 404)

    def test_pet_lifecycle_with_photo(self):
        created = self.client.post("/api/pets", json={"name": "Mingau", "species": "CAT", "photo_data": photo_data_url()})
        self.assertEqual(created.status_code, 201)
        pet_id = created.json()["id"]
        self.assertEqual(len(self.client.get("/api/pets").json()["pets"]), 1)
        photo = self.client.get(f"/api/pets/{pet_id}/photo")
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo.headers["content-type"], "image/jpeg")
        self.assertEqual(self.client.get(f"/api/pets/{pet_id}/references").json(), {"images": []})
        self.assertEqual(self.client.delete(f"/api/pets/{pet_id}").status_code, 204)
        self.assertEqual(self.client.get("/api/pets").json(), {"pets": []})

    @patch("app.services.camera.service.device_information", return_value={})
    @patch("app.services.camera.service.resolve_connection_urls", return_value=[])
    def test_camera_and_zone_lifecycle_without_network(self, _urls, _identity):
        created = self.client.post("/api/cameras", json={"name": "Sala", "ip": "192.168.1.50"})
        self.assertEqual(created.status_code, 201)
        camera = created.json()
        self.assertFalse(camera["status"]["connected"])
        self.assertEqual(self.client.post("/api/cameras", json={"name": "Outra", "ip": "192.168.1.50"}).status_code, 409)
        self.assertEqual(len(self.client.get("/api/cameras").json()["cameras"]), 1)
        self.assertEqual(self.client.get(f"/api/cameras/{camera['id']}/video").status_code, 422)
        self.assertEqual(self.client.get(f"/api/monitoring/{camera['id']}").json()["status"], "model_missing")

        zone = self.client.post("/api/zones", json={"camera_id": camera["id"], "name": "Água", "type": "WATER", "polygon": SQUARE})
        self.assertEqual(zone.status_code, 201)
        degenerate = [{"x": 0.1, "y": 0.1}, {"x": 0.1, "y": 0.1}, {"x": 0.1, "y": 0.1}]
        self.assertEqual(
            self.client.post("/api/zones", json={"camera_id": camera["id"], "name": "Ruim", "type": "FOOD", "polygon": degenerate}).status_code,
            422,
        )
        self.assertEqual(len(self.client.get("/api/zones").json()["zones"]), 1)
        self.assertEqual(self.client.delete(f"/api/zones/{zone.json()['id']}").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/cameras/{camera['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/health").json()["cameras"]["registered"], 0)

    def test_empty_collections_and_spa_without_build(self):
        self.assertEqual(self.client.get("/api/events").json()["total"], 0)
        self.assertEqual(self.client.get("/api/identification/logs").json()["analyses"], [])
        settings = self.client.get("/api/settings").json()
        self.assertEqual(settings["retention_days"], 7)
        self.assertFalse(settings["auto_review_enabled"])
        self.assertIsNone(settings["auto_review_minimum_similarity"])
        self.assertEqual(self.client.get("/").status_code, 503)
        self.assertEqual(self.client.get("/api/nao-existe").status_code, 404)


if __name__ == "__main__":
    unittest.main()
