import tempfile
import unittest
from pathlib import Path

from app.domain.enums import ReviewDecision, ZoneType
from app.domain.errors import InvalidDomainValueError
from app.domain.clock import local_today, utc_now
from app.infra.database.database import Database
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.pet_repository import PetRepository
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.ai.pet_identifier import PetIdentifier
from app.services.commands import ReviewEventCommand
from app.infra.ai.identification_calibration import IdentificationCalibrator
from app.services.event_query_service import EventQueryService
from app.services.event_review_service import EventReviewService


class EventHistoryAndReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")
        self.database.migrate()
        now = utc_now()
        self.today = local_today().isoformat()
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
        self.service = EventReviewService(self.events, self.pets, None)
        self.queries = EventQueryService(self.events)

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

        first = self.queries.search(1, 10, zone_type=ZoneType.WATER)
        second = self.queries.search(2, 10, zone_type=ZoneType.WATER)
        third = self.queries.search(3, 10, zone_type=ZoneType.WATER)

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

    def test_human_review_can_override_incorrect_detected_species(self):
        self.database.execute(
            """INSERT INTO events
               (id, camera_id, zone_id, started_at, detected_species, created_at)
               VALUES (?, ?, ?, ?, 'DOG', ?)""",
            ("wrong-species", "camera-1", "water-zone", f"{self.today}T12:00:00+00:00", utc_now()),
        )

        self.review("wrong-species", ReviewDecision.CONFIRMED, self.pet["id"])

        self.assertEqual(self.events.get("wrong-species")["pet_id"], self.pet["id"])

    def test_review_can_replace_automatically_identified_cat(self):
        other_pet = self.pets.create("Luna", "CAT", "", "pets/profiles/luna.jpg")
        self.database.execute(
            """INSERT INTO events
               (id, camera_id, zone_id, started_at, detected_species, pet_capture_path,
                pet_id, automatically_identified_pet_id, pet_identification_confidence,
                pet_identification_method, created_at)
               VALUES (?, ?, ?, ?, 'CAT', ?, ?, ?, ?, ?, ?)""",
            (
                "auto-cat", "camera-1", "water-zone", f"{self.today}T12:00:00+00:00",
                "pets/captures/cat.jpg", self.pet["id"], self.pet["id"], 0.91,
                "appearance-histogram-v1", utc_now(),
            ),
        )

        self.review("auto-cat", ReviewDecision.CONFIRMED, other_pet["id"])

        event = self.events.get("auto-cat")
        self.assertEqual(event["pet_id"], other_pet["id"])
        self.assertEqual(event["automatically_identified_pet_id"], self.pet["id"])
        reference = self.database.one(
            "SELECT pet_id FROM pet_reference_images WHERE event_id = ?", ("auto-cat",)
        )
        self.assertEqual(reference["pet_id"], other_pet["id"])

    def test_tenth_review_persists_new_identification_calibration(self):
        identifications = PetIdentificationRepository(self.database)
        service = EventReviewService(self.events, self.pets, IdentificationCalibrator(identifications))
        for index in range(10):
            event_id = f"learning-{index}"
            self.create_event(event_id)
            identifications.create_analysis(
                event_id, "CAT", None, "MATCHED", self.pet["id"], 0.88, 0.72, 0.08,
                [{"pet_id": self.pet["id"], "confidence": 0.88, "reference_count": 1}],
                PetIdentifier.METHOD,
            )
            service.review(
                event_id,
                ReviewEventCommand(
                    decision=ReviewDecision.CONFIRMED,
                    corrected_activity=None,
                    pet_id=self.pet["id"],
                    notes=None,
                    zone_type=None,
                ),
            )

        calibration = identifications.current_calibration()
        logs = identifications.list_analyses()
        self.assertEqual(calibration["interaction_count"], 10)
        self.assertEqual(calibration["accuracy"], 1.0)
        self.assertEqual(identifications.count_analyses(), 10)
        self.assertEqual(len(identifications.list_analyses(3, 2)), 3)
        self.assertEqual(logs[0]["scores"][0]["pet_name"], "Mingau")

    def test_correction_requires_a_different_supported_zone_type(self):
        self.create_event("invalid-correction")

        with self.assertRaises(InvalidDomainValueError):
            self.review("invalid-correction", ReviewDecision.CORRECTED, zone_type=ZoneType.CUSTOM)

        with self.assertRaises(InvalidDomainValueError):
            self.review("invalid-correction", ReviewDecision.CORRECTED, zone_type=ZoneType.WATER)

    def test_reference_image_can_be_removed_without_deleting_event(self):
        self.create_event("reference-event", capture_path="pets/captures/cat.jpg")
        self.review("reference-event", ReviewDecision.CONFIRMED, self.pet["id"])
        reference = self.pets.list_reference_images(self.pet["id"])[0]

        self.assertTrue(self.pets.delete_reference_image(self.pet["id"], reference["id"]))

        self.assertEqual(self.pets.list_reference_images(self.pet["id"]), [])
        self.assertIsNotNone(self.events.get("reference-event"))


if __name__ == "__main__":
    unittest.main()
