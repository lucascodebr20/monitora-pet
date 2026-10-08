import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging_setup import reset_logging
from app.main import create_app
from tests.test_routes import photo_data_url

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def jpeg(value=90, edge=900) -> bytes:
    encoded, content = cv2.imencode(".jpg", np.full((edge, edge, 3), value, dtype=np.uint8))
    assert encoded
    return content.tobytes()


class PetHealthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.settings = Settings(data_dir=root / "data", frontend_dist=root / "dist")
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()
        self.pet = self.create_pet("Ciri")
        self.base = f"/api/pets/{self.pet}/health"

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        reset_logging()
        self.temp.cleanup()

    def create_pet(self, name: str) -> str:
        response = self.client.post("/api/pets", json={"name": name, "species": "CAT", "photo_data": photo_data_url()})
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def upload(self, path: str, content: bytes, filename: str):
        return self.client.post(path, params={"filename": filename}, content=content,
                                headers={"Content-Type": "application/octet-stream"})

    def test_replacing_food_closes_the_current_period_and_keeps_history(self):
        first = self.client.post(f"{self.base}/food", json={
            "name": "Renal", "brand": "Royal", "food_type": "DRY", "started_on": "2026-09-01"})
        self.assertEqual(first.status_code, 201)
        wet = self.client.post(f"{self.base}/food", json={"name": "Sachê", "food_type": "WET", "started_on": "2026-09-10"})
        self.assertEqual(wet.status_code, 201)
        replaced = self.client.post(f"{self.base}/food", json={
            "name": "Urinary", "food_type": "DRY", "started_on": "2026-10-01", "replace_current": True})
        self.assertEqual(replaced.status_code, 201)
        items = {item["name"]: item for item in self.client.get(f"{self.base}/food").json()["items"]}
        self.assertEqual(items["Renal"]["ended_on"], "2026-10-01")
        self.assertEqual(items["Sachê"]["ended_on"], "2026-10-01")
        self.assertIsNone(items["Urinary"]["ended_on"])
        invalid = self.client.post(f"{self.base}/food", json={
            "name": "X", "food_type": "DRY", "started_on": "2026-10-05", "ended_on": "2026-10-01"})
        self.assertEqual(invalid.status_code, 422)

    def test_exam_keeps_original_files_with_thumbnails_and_rejects_duplicates(self):
        exam = self.client.post(f"{self.base}/exams", json={
            "title": "Hemograma", "exam_type": "BLOOD", "performed_on": "2026-10-02", "laboratory": "VetLab"}).json()
        path = f"{self.base}/exams/{exam['id']}/attachments"
        pdf = self.upload(path, PDF, "laudo.pdf")
        self.assertEqual(pdf.status_code, 201)
        self.assertIsNone(pdf.json()["thumbnail_url"])
        photo = self.upload(path, jpeg(), "pagina 2.jpg")
        self.assertEqual(photo.status_code, 201)
        self.assertEqual(self.upload(path, PDF, "de novo.pdf").status_code, 409)
        self.assertEqual(self.upload(path, b"MZ executavel", "virus.pdf").status_code, 422)

        listed = self.client.get(f"{self.base}/exams").json()["items"][0]
        self.assertEqual([item["original_name"] for item in listed["attachments"]], ["laudo.pdf", "pagina 2.jpg"])
        original = self.client.get(pdf.json()["url"])
        self.assertEqual(original.content, PDF)
        self.assertEqual(original.headers["content-type"], "application/pdf")
        thumbnail = self.client.get(photo.json()["thumbnail_url"])
        decoded = cv2.imdecode(np.frombuffer(thumbnail.content, np.uint8), cv2.IMREAD_COLOR)
        self.assertLessEqual(max(decoded.shape[:2]), 480)

        files = list((self.settings.health_dir).rglob("*.*"))
        self.assertEqual(len(files), 3)
        self.assertEqual(self.client.delete(f"{self.base}/exams/{exam['id']}").status_code, 204)
        self.assertEqual(list(self.settings.health_dir.rglob("*.*")), [])

    def test_records_are_scoped_to_their_pet(self):
        other = self.create_pet("Tom")
        exam = self.client.post(f"{self.base}/exams", json={"title": "Urina", "exam_type": "URINE"}).json()
        attachment = self.upload(f"{self.base}/exams/{exam['id']}/attachments", PDF, "a.pdf").json()
        other_base = f"/api/pets/{other}/health"
        self.assertEqual(self.client.get(f"{other_base}/exams").json()["items"], [])
        self.assertEqual(self.client.get(f"{other_base}/attachments/{attachment['id']}").status_code, 404)
        self.assertEqual(self.upload(f"{other_base}/exams/{exam['id']}/attachments", jpeg(), "b.jpg").status_code, 404)
        self.assertEqual(self.client.delete(f"{other_base}/exams/{exam['id']}").status_code, 404)

    def test_treatment_groups_doses_and_photo_entries(self):
        treatment = self.client.post(f"{self.base}/treatments", json={
            "title": "Ferida na pata", "body_region": "pata traseira", "started_on": "2026-10-01"}).json()
        dose = self.client.post(f"{self.base}/doses", json={
            "kind": "MEDICATION", "name": "Antibiótico", "dose": "1/2 comp.", "given_on": "2026-10-01",
            "treatment_id": treatment["id"]})
        self.assertEqual(dose.status_code, 201)
        entry = self.client.post(f"{self.base}/treatments/{treatment['id']}/entries", json={
            "observed_at": "2026-10-03T20:15:00-03:00", "notes": "menos vermelho"}).json()
        self.assertEqual(entry["observed_at"], "2026-10-03T23:15:00+00:00")
        photo = self.upload(f"{self.base}/treatments/{treatment['id']}/entries/{entry['id']}/attachments", jpeg(), "d3.jpg")
        self.assertEqual(photo.status_code, 201)

        listed = self.client.get(f"{self.base}/treatments").json()["items"][0]
        self.assertEqual(listed["doses"][0]["name"], "Antibiótico")
        self.assertEqual(len(listed["entries"][0]["attachments"]), 1)
        self.assertEqual(self.client.delete(f"{self.base}/treatments/{treatment['id']}").status_code, 204)
        self.assertEqual(list(self.settings.health_dir.rglob("*.*")), [])
        self.assertIsNone(self.client.get(f"{self.base}/doses").json()["items"][0]["treatment_id"])

    def test_reminders_follow_the_latest_dose_of_each_vaccine(self):
        today = date.today()
        self.client.post(f"{self.base}/doses", json={
            "kind": "VACCINE", "name": "V4", "given_on": (today - timedelta(days=365)).isoformat(),
            "next_due_on": (today - timedelta(days=2)).isoformat()})
        self.client.post(f"{self.base}/doses", json={
            "kind": "VACCINE", "name": "Raiva", "given_on": (today - timedelta(days=360)).isoformat(),
            "next_due_on": (today + timedelta(days=5)).isoformat()})
        self.client.post(f"{self.base}/doses", json={
            "kind": "VACCINE", "name": "Raiva", "given_on": today.isoformat(),
            "next_due_on": (today + timedelta(days=365)).isoformat()})
        reminders = self.client.get("/api/health-reminders").json()["reminders"]
        self.assertEqual([(item["name"], item["overdue"]) for item in reminders], [("V4", True)])
        self.assertEqual(self.client.get(f"{self.base}/summary").json()["reminders"][0]["days_until_due"], -2)

    def test_timeline_merges_records_with_camera_days(self):
        self.client.post(f"{self.base}/weights", json={"measured_on": "2026-10-02", "weight_kg": 4.25})
        self.client.post(f"{self.base}/food", json={"name": "Urinary", "food_type": "DRY", "started_on": "2026-10-01"})
        noon = datetime(2026, 10, 2, 12, tzinfo=timezone.utc).astimezone()
        with closing(sqlite3.connect(self.settings.database_path)) as connection:
            connection.execute("INSERT INTO cameras (id, name, ip, created_at, updated_at) VALUES ('c', 'Sala', '1.1.1.1', 'x', 'x')")
            connection.execute("""INSERT INTO zones (id, camera_id, name, type, polygon, created_at, updated_at)
                                  VALUES ('z', 'c', 'Caixa', 'LITTER', '[]', 'x', 'x')""")
            for index, decision in enumerate(("CONFIRMED", None, "NO_ACTION")):
                connection.execute(
                    """INSERT INTO events (id, camera_id, zone_id, started_at, confidence, activity, engine_version,
                                           created_at, pet_id)
                       VALUES (?, 'c', 'z', ?, 0.9, 'USING_LITTER', 'test', 'x', ?)""",
                    (f"e{index}", (noon + timedelta(minutes=index)).astimezone(timezone.utc).isoformat(), self.pet),
                )
                if decision:
                    connection.execute(
                        """INSERT INTO human_reviews (id, event_id, decision, created_at, pet_id)
                           VALUES (?, ?, ?, 'x', ?)""", (f"r{index}", f"e{index}", decision, self.pet))
            connection.commit()
        timeline = self.client.get(f"{self.base}/timeline", params={"start": "2026-10-01", "end": "2026-10-03"}).json()
        kinds = [(item["date"], item["kind"]) for item in timeline["items"]]
        day = noon.date().isoformat()
        self.assertIn((day, "CAMERA_DAY"), kinds)
        self.assertIn(("2026-10-02", "WEIGHT"), kinds)
        self.assertIn(("2026-10-01", "FOOD_START"), kinds)
        camera = next(item for item in timeline["items"] if item["kind"] == "CAMERA_DAY")
        self.assertEqual(camera["counts"], {"LITTER": {"detected": 2, "confirmed": 1}})
        self.assertEqual(self.client.get(f"{self.base}/timeline", params={"start": "2026-10-05", "end": "2026-10-01"}).status_code, 422)

    def test_deleting_pet_removes_its_health_files(self):
        exam = self.client.post(f"{self.base}/exams", json={"title": "Raio-X", "exam_type": "IMAGING"}).json()
        self.upload(f"{self.base}/exams/{exam['id']}/attachments", jpeg(), "rx.jpg")
        self.assertTrue(list(self.settings.health_dir.rglob("*.*")))
        self.assertEqual(self.client.delete(f"/api/pets/{self.pet}").status_code, 204)
        self.assertEqual(list(self.settings.health_dir.rglob("*.*")), [])


if __name__ == "__main__":
    unittest.main()
