import tempfile
import unittest
from pathlib import Path

from app.domain.errors import InvalidDomainValueError
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.repositories.pet_repository import PetRepository
from app.infra.repositories.settings_repository import SettingsRepository
from app.services.event.auto_review import MINIMUM_SAMPLES, AutoReviewService
from tests.test_monitoring import build_repositories, square_zone


class AutoReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.directory.name)
        self.database, self.camera_repository, self.zone_repository, self.event_repository = build_repositories(
            self.directory.name
        )
        self.settings = SettingsRepository(self.database)
        self.identification = PetIdentificationRepository(self.database)
        self.pets = PetRepository(self.database)
        self.camera = self.camera_repository.create({"name": "Sala", "ip": "192.168.1.10"})
        self.zone = self.zone_repository.create(square_zone(self.camera["id"], "Comida", "FOOD", 0))
        self.service = AutoReviewService(self.settings, self.event_repository, self.identification)

    def tearDown(self):
        self.directory.cleanup()

    def _pet(self, name):
        return self.pets.create(name, "CAT", "", None)

    def _event(self, pet_id, confidence):
        return self.event_repository.create_detected_event(
            self.camera["id"], self.zone["id"], "2026-10-10T12:00:00+00:00", "2026-10-10T12:01:00+00:00",
            0.9, None, "CAT", None, pet_id, confidence, "mobilenet-embedding-v2",
        )

    def _analysis(self, event_id, winner, winner_confidence, runner_up, runner_up_confidence, reviewed_pet_id):
        self.identification.create_analysis(
            event_id, "CAT", None, "MATCHED", winner, winner_confidence, 0.7, 0.0,
            [
                {"pet_id": winner, "confidence": winner_confidence, "reference_count": 10},
                {"pet_id": runner_up, "confidence": runner_up_confidence, "reference_count": 10},
            ],
            "mobilenet-embedding-v2",
        )
        self.identification.mark_review(event_id, reviewed_pet_id)

    def _seed(self, count, winner_confidence=0.9, runner_up_confidence=0.5, correct=True):
        first, second = self._pet("Tom"), self._pet("Ciri")
        for _ in range(count):
            event_id = self._event(first["id"], winner_confidence)
            self._analysis(
                event_id, first["id"], winner_confidence, second["id"], runner_up_confidence,
                first["id"] if correct else second["id"],
            )
        return first, second

    def test_disabled_by_default(self):
        self.assertFalse(self.service.enabled())
        self.assertEqual(self.service.target_precision(), 0.97)

    def test_rejects_target_precision_out_of_range(self):
        with self.assertRaises(InvalidDomainValueError):
            self.service.update(True, 0.5)

    def test_does_not_confirm_without_enough_reviewed_samples(self):
        self._seed(MINIMUM_SAMPLES - 1)
        self.service.update(True, 0.97)
        self.assertIsNone(self.service.thresholds())
        self.assertFalse(self.service.should_confirm("pet", 0.99, 0.5))

    def test_confirms_once_samples_support_the_target(self):
        self._seed(MINIMUM_SAMPLES)
        self.service.update(True, 0.97)
        self.assertIsNotNone(self.service.thresholds())
        self.assertTrue(self.service.should_confirm("pet", 0.95, 0.4))

    def test_never_confirms_while_disabled(self):
        self._seed(MINIMUM_SAMPLES)
        self.service.update(False, 0.97)
        self.assertFalse(self.service.should_confirm("pet", 0.99, 0.5))

    def test_does_not_confirm_when_the_data_never_reaches_the_target(self):
        self._seed(MINIMUM_SAMPLES, correct=False)
        self.service.update(True, 0.97)
        self.assertIsNone(self.service.thresholds())

    def test_automatic_review_does_not_feed_the_calibration(self):
        """O ponto central: a revisão automática não pode treinar o identificador."""
        pet = self._pet("Vlad")
        event_id = self._event(pet["id"], 0.95)
        self.identification.create_analysis(
            event_id, "CAT", None, "MATCHED", pet["id"], 0.95, 0.7, 0.0,
            [{"pet_id": pet["id"], "confidence": 0.95, "reference_count": 10}], "mobilenet-embedding-v2",
        )
        before = self.identification.reviewed_count("mobilenet-embedding-v2")

        self.service.confirm(event_id, pet["id"])

        self.assertEqual(self.identification.reviewed_count("mobilenet-embedding-v2"), before)
        self.assertTrue(self.event_repository.has_review(event_id))
        row = self.database.one("SELECT automatic FROM human_reviews WHERE event_id = ?", (event_id,))
        self.assertEqual(int(row["automatic"]), 1)

    def test_automatic_review_does_not_create_a_reference_image(self):
        """Promover um palpite a referência contaminaria as comparações seguintes."""
        pet = self._pet("Vlad")
        event_id = self._event(pet["id"], 0.95)
        self.service.confirm(event_id, pet["id"])
        row = self.database.one("SELECT COUNT(*) AS total FROM pet_reference_images WHERE pet_id = ?", (pet["id"],))
        self.assertEqual(int(row["total"]), 0)

    def test_view_reports_why_it_is_not_acting_yet(self):
        view = self.service.view()
        self.assertEqual(view["auto_review_sample_count"], 0)
        self.assertEqual(view["auto_review_minimum_samples"], MINIMUM_SAMPLES)
        self.assertIsNone(view["auto_review_expected_coverage"])


if __name__ == "__main__":
    unittest.main()
