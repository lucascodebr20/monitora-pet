import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.domain.enums import ReviewDecision, ZoneType
from app.domain.errors import InvalidDomainValueError
from app.infra.database.database import Database, utc_now
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.pet_repository import PetRepository
from app.services.commands import ReviewEventCommand
from app.services.event_service import EventService
from app.infra.media.clip_store import ClipStore
from app.infra.media.snapshot_store import SnapshotStore


class EventHistoryAndReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")
        self.database.migrate()
        now = utc_now()
        self.today = datetime.now(timezone.utc).date().isoformat()
        self.database.execute(
            "INSERT INTO cameras (id, name, ip, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("camera-1", "Sala", "192.168.1.20", now, now),
        )
        self.database.execute(
            """INSERT INTO zones (id, camera_id, name, type, polygon, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("water-zone", "camera-1", "Bebedouro", "WATER", "[]", now, now),
        )
        self.database.execute(
            """INSERT INTO zones (id, camera_id, name, type, polygon, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("food-zone", "camera-1", "Comedouro", "FOOD", "[]", now, now),
        )
        self.events = EventRepository(self.database)
        self.pets = PetRepository(self.database)
        self.pet = self.pets.create("Mingau", "CAT", "", "pets/profiles/mingau.jpg")
        self.service = EventService(self.events, SnapshotStore(), ClipStore(), self.pets, None)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_event(self, event_id, zone_id="water-zone", capture_path=None):
        self.database.execute(
            """INSERT INTO events
               (id, camera_id, zone_id, started_at, detected_species, pet_capture_path, created_at)
               VALUES (?, ?, ?, ?, 'CAT', ?, ?)""",
            (event_id, "camera-1", zone_id, f"{self.today}T12:00:00+00:00", capture_path, utc_now()),
        )

    def review(self, event_id, decision, pet_id=None, zone_type=None):
        return self.service.review(
            event_id,
            ReviewEventCommand(
                decision=decision,
                corrected_activity=None,
                pet_id=pet_id,
                notes=None,
                zone_type=zone_type,
            ),
        )

    def test_search_returns_real_pages_and_total_for_filters(self):
        for index in range(23):
            self.create_event(f"water-{index}")
        for index in range(3):
            self.create_event(f"food-{index}", "food-zone")

        first = self.service.search(1, 10, zone_type=ZoneType.WATER)
        second = self.service.search(2, 10, zone_type=ZoneType.WATER)
        third = self.service.search(3, 10, zone_type=ZoneType.WATER)

        self.assertEqual(first["total"], 23)
        self.assertEqual([len(first["events"]), len(second["events"]), len(third["events"])], [10, 10, 3])
        self.assertTrue(all(event["zone_type"] == "WATER" for event in second["events"]))

    def test_corrected_type_is_saved_on_event_and_not_zone(self):
        self.create_event("correct-me", capture_path="pets/captures/cat.jpg")

        self.review("correct-me", ReviewDecision.CORRECTED, self.pet["id"], ZoneType.FOOD)

        self.assertEqual(self.events.get("correct-me")["corrected_zone_type"], "FOOD")
        self.assertEqual(self.events.list()[0]["zone_type"], "FOOD")
        self.assertEqual(self.database.one("SELECT type FROM zones WHERE id = 'water-zone'")["type"], "WATER")
        self.assertEqual(self.pets.list()[0]["reference_count"], 1)
        self.assertEqual(self.events.count_by_zone_type_on_date(self.today)["FOOD"], 1)

    def test_rejected_evidence_stays_in_history_but_not_visit_totals(self):
        self.create_event("reject-me")

        self.review("reject-me", ReviewDecision.FALSE_POSITIVE)

        self.assertEqual(self.events.list()[0]["review_decision"], "FALSE_POSITIVE")
        self.assertEqual(self.events.count_on_date(self.today), 0)
        self.assertEqual(self.events.count_by_zone_type_on_date(self.today)["WATER"], 0)

    def test_acceptance_without_pet_is_allowed(self):
        self.create_event("unknown-pet")

        self.review("unknown-pet", ReviewDecision.CONFIRMED)

        self.assertIsNone(self.events.get("unknown-pet")["pet_id"])
        self.assertEqual(self.events.count_on_date(self.today), 1)

    def test_correction_requires_a_different_supported_zone_type(self):
        self.create_event("invalid-correction")

        with self.assertRaises(InvalidDomainValueError):
            self.review("invalid-correction", ReviewDecision.CORRECTED, zone_type=ZoneType.CUSTOM)

        with self.assertRaises(InvalidDomainValueError):
            self.review("invalid-correction", ReviewDecision.CORRECTED, zone_type=ZoneType.WATER)


if __name__ == "__main__":
    unittest.main()
