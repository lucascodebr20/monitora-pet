import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.enums import ReviewDecision, ZoneType
from app.domain.errors import InvalidDomainValueError
from app.domain.clock import local_today, utc_bounds_for_local_date, utc_now
from app.infra.database.database import Database
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.pet_repository import PetRepository
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.ai.pet_identifier import PetIdentifier
from app.services.event import EventQueryService, EventReviewService, ReviewEventCommand
from app.infra.ai.identification_calibration import IdentificationCalibrator


class ReviewTestBase(unittest.TestCase):
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

    def create_event_on_date(self, event_id, value):
        start, end = utc_bounds_for_local_date(value)
        instant = datetime.fromisoformat(start) + (datetime.fromisoformat(end) - datetime.fromisoformat(start)) / 2
        self.database.execute(
            """INSERT INTO events
               (id, camera_id, zone_id, started_at, detected_species, created_at)
               VALUES (?, 'camera-1', 'water-zone', ?, 'CAT', ?)""",
            (event_id, instant.isoformat(), utc_now()),
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


class EventHistoryAndReviewTests(ReviewTestBase):
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

    def test_search_filters_inclusive_local_date_range(self):
        today = local_today()
        dates = [(today - timedelta(days=2)).isoformat(), (today - timedelta(days=1)).isoformat(), today.isoformat()]
        for index, value in enumerate(dates):
            self.create_event_on_date(f"range-{index}", value)

        result = self.queries.search(1, 10, start_date=dates[1], end_date=dates[2])

        self.assertEqual(result["total"], 2)
        self.assertEqual({event["id"] for event in result["events"]}, {"range-1", "range-2"})

    def test_search_rejects_reversed_date_range(self):
        with self.assertRaises(InvalidDomainValueError):
            self.queries.search(1, 10, start_date="2026-10-06", end_date="2026-10-05")

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


class NoActionAndMultiplePetsTests(ReviewTestBase):
    """Desfechos para 'o gato certo nao usou a area' e 'mais de um gato'."""

    def review_pets(self, event_id, pet_ids):
        return self.service.review(
            event_id,
            ReviewEventCommand(
                decision=ReviewDecision.MULTIPLE_PETS,
                corrected_activity=None,
                pet_id=None,
                notes=None,
                zone_type=None,
                pet_ids=tuple(pet_ids),
            ),
        )

    def test_no_action_keeps_the_pet_and_trains_the_identifier(self):
        """O gato estava certo: a identificacao precisa contar como acerto."""
        self.create_event("event-1", capture_path="pets/captures/a.jpg")
        self.review("event-1", ReviewDecision.NO_ACTION, pet_id=self.pet["id"])

        event = self.events.get("event-1")
        self.assertEqual(event["pet_id"], self.pet["id"])
        row = self.database.one("SELECT decision FROM human_reviews WHERE event_id = ?", ("event-1",))
        self.assertEqual(row["decision"], "NO_ACTION")

    def test_no_action_requires_a_pet(self):
        self.create_event("event-2")
        with self.assertRaises(InvalidDomainValueError):
            self.review("event-2", ReviewDecision.NO_ACTION)

    def test_no_action_leaves_the_visit_out_of_the_counters(self):
        """Mesma contagem de antes: voce recusava esses eventos."""
        self.create_event("event-3")
        self.review("event-3", ReviewDecision.NO_ACTION, pet_id=self.pet["id"])
        self.assertEqual(self.events.count_on_date(self.today), 0)

    def test_multiple_pets_records_every_cat_without_choosing_one(self):
        other = self.pets.create("Amora", "CAT", "", None)
        self.create_event("event-4", capture_path="pets/captures/b.jpg")

        self.review_pets("event-4", [self.pet["id"], other["id"]])

        event = self.events.get("event-4")
        self.assertIsNone(event["pet_id"])
        rows = self.database.all("SELECT pet_id FROM event_pets WHERE event_id = ?", ("event-4",))
        self.assertEqual({row["pet_id"] for row in rows}, {self.pet["id"], other["id"]})

    def test_multiple_pets_never_becomes_a_reference_image(self):
        """A captura tem dois gatos: promove-la contaminaria a galeria."""
        other = self.pets.create("Amora", "CAT", "", None)
        self.create_event("event-5", capture_path="pets/captures/c.jpg")
        self.review_pets("event-5", [self.pet["id"], other["id"]])
        row = self.database.one("SELECT COUNT(*) AS total FROM pet_reference_images")
        self.assertEqual(int(row["total"]), 0)

    def test_multiple_pets_still_counts_as_a_visit(self):
        other = self.pets.create("Amora", "CAT", "", None)
        self.create_event("event-6")
        self.review_pets("event-6", [self.pet["id"], other["id"]])
        self.assertEqual(self.events.count_on_date(self.today), 1)

    def test_multiple_pets_requires_at_least_two(self):
        self.create_event("event-7")
        with self.assertRaises(InvalidDomainValueError):
            self.review_pets("event-7", [self.pet["id"]])

    def test_history_filter_finds_events_with_several_cats(self):
        other = self.pets.create("Amora", "CAT", "", None)
        self.create_event("event-8")
        self.review_pets("event-8", [self.pet["id"], other["id"]])

        result = self.queries.search(page=1, page_size=10, pet_id=other["id"])

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["events"][0]["pet_names"], "Amora, Mingau")
