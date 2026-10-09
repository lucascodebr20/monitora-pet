import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from app.infra.ai.identification_calibration import IdentificationCalibrator
from app.infra.ai.pet_identifier import PetIdentifier


class FakePetRepository:
    def __init__(self, pets, references=None):
        self.pets = pets
        self.references = references or {}

    def list_by_species(self, species):
        return [pet for pet in self.pets if pet["species"] == species]

    def list_reference_images(self, pet_id):
        return self.references.get(pet_id, [])


class FakeImageStore:
    def __init__(self, root):
        self.root = root

    def resolve(self, relative_path):
        return self.root / relative_path


class FakeLearningRepository:
    def __init__(self):
        self.reviewed = 0
        self.calibrations = []

    def current_calibration(self, method=None, species=None):
        if self.calibrations:
            return self.calibrations[-1]
        return {"minimum_similarity": 0.72, "minimum_margin": 0.08, "interaction_count": 0, "accuracy": None}

    def mark_review(self, event_id, pet_id):
        self.reviewed += 1
        return "CAT"

    def reviewed_count(self, method=None, species=None):
        return self.reviewed

    def reviewed_samples(self, method=None, species=None):
        return [
            {
                "selected_pet_id": "mingau",
                "reviewed_pet_id": "mingau",
                "scores": [
                    {"pet_id": "mingau", "confidence": 0.88},
                    {"pet_id": "luna", "confidence": 0.42},
                ],
            }
            for _ in range(self.reviewed)
        ]

    def create_calibration(self, minimum_similarity, minimum_margin, interaction_count, accuracy, method=None, species=None):
        self.calibrations.append({
            "minimum_similarity": minimum_similarity,
            "minimum_margin": minimum_margin,
            "interaction_count": interaction_count,
            "accuracy": accuracy,
            "method": method,
        })


class PetIdentifierTests(unittest.TestCase):
    @staticmethod
    def write_image(path, color):
        image = np.full((120, 120, 3), color, dtype=np.uint8)
        cv2.imwrite(str(path), image)

    def test_identifies_cat_with_closest_visual_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_image(root / "capture.jpg", (15, 35, 185))
            self.write_image(root / "mingau.jpg", (15, 35, 185))
            self.write_image(root / "luna.jpg", (180, 35, 15))
            repository = FakePetRepository([
                {"id": "mingau", "species": "CAT", "photo_path": "mingau.jpg"},
                {"id": "luna", "species": "CAT", "photo_path": "luna.jpg"},
            ])

            match = PetIdentifier(repository, FakeImageStore(root)).analyze("capture.jpg", "CAT").match

            self.assertIsNotNone(match)
            self.assertEqual(match.pet_id, "mingau")
            self.assertGreaterEqual(match.confidence, PetIdentifier.MINIMUM_SIMILARITY)

    def test_does_not_assign_when_two_cats_are_visually_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("capture.jpg", "first.jpg", "second.jpg"):
                self.write_image(root / name, (40, 80, 140))
            repository = FakePetRepository([
                {"id": "first", "species": "CAT", "photo_path": "first.jpg"},
                {"id": "second", "species": "CAT", "photo_path": "second.jpg"},
            ])

            match = PetIdentifier(repository, FakeImageStore(root)).analyze("capture.jpg", "CAT").match

            self.assertIsNone(match)

    def test_identifies_dogs_only_among_dog_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_image(root / "capture.jpg", (30, 60, 200))
            self.write_image(root / "rex.jpg", (30, 60, 200))
            self.write_image(root / "mingau.jpg", (30, 60, 200))
            repository = FakePetRepository([
                {"id": "rex", "species": "DOG", "photo_path": "rex.jpg"},
                {"id": "mingau", "species": "CAT", "photo_path": "mingau.jpg"},
            ])

            analysis = PetIdentifier(repository, FakeImageStore(root)).analyze("capture.jpg", "DOG")

            self.assertEqual(analysis.decision, "MATCHED")
            self.assertEqual(analysis.match.pet_id, "rex")
            self.assertEqual([score["pet_id"] for score in analysis.scores], ["rex"])

    def pair_identifier(self, references_per_pet):
        generator = np.random.default_rng(7)
        vectors = {}
        references = {}
        for pet_id, side in (("tom", 1.0), ("ciri", -1.0)):
            references[pet_id] = []
            for index in range(references_per_pet):
                vector = generator.normal(0.0, 0.3, 8)
                vector[0] = side + generator.normal(0.0, 0.1)
                path = f"{pet_id}-{index}.jpg"
                vectors[path] = vector / np.linalg.norm(vector)
                references[pet_id].append({"image_path": path})
        capture = generator.normal(0.0, 0.3, 8)
        capture[0] = 0.8
        identifier = PetIdentifier(FakePetRepository([
            {"id": "tom", "species": "CAT"}, {"id": "ciri", "species": "CAT"},
        ], references), FakeImageStore(Path(".")))
        identifier._descriptor = lambda image: capture / np.linalg.norm(capture)
        identifier._descriptor_for_path = lambda path: (vectors[path], 1.0) if path in vectors else None
        identifier._gallery_score = lambda descriptor, items: 0.9
        return identifier

    def test_pair_classifier_decides_between_two_similar_pets(self):
        analysis = self.pair_identifier(PetIdentifier.PAIR_MINIMUM_REFERENCES).analyze_images(
            [np.zeros((4, 4, 3), dtype=np.uint8)], "CAT")
        self.assertEqual(analysis.decision, "MATCHED")
        self.assertEqual(analysis.match.pet_id, "tom")

    def test_pair_classifier_waits_for_enough_reviewed_references(self):
        analysis = self.pair_identifier(PetIdentifier.PAIR_MINIMUM_REFERENCES - 1).analyze_images(
            [np.zeros((4, 4, 3), dtype=np.uint8)], "CAT")
        self.assertEqual(analysis.decision, "AMBIGUOUS")
        self.assertIsNone(analysis.match)

    def test_pair_classifier_still_requires_minimum_similarity(self):
        identifier = self.pair_identifier(PetIdentifier.PAIR_MINIMUM_REFERENCES)
        identifier._gallery_score = lambda descriptor, items: 0.2
        analysis = identifier.analyze_images([np.zeros((4, 4, 3), dtype=np.uint8)], "CAT")
        self.assertEqual(analysis.decision, "LOW_SIMILARITY")

    def test_unknown_species_is_not_analyzed(self):
        repository = FakePetRepository([])
        analysis = PetIdentifier(repository, FakeImageStore(Path("."))).analyze("capture.jpg", "BIRD")
        self.assertEqual(analysis.decision, "UNSUPPORTED")

    def test_recalibrates_thresholds_after_each_ten_confirmed_interactions(self):
        learning = FakeLearningRepository()
        identifier = IdentificationCalibrator(learning)

        for index in range(9):
            identifier.learn_from_review(f"event-{index}", "mingau")
        self.assertEqual(learning.calibrations, [])

        identifier.learn_from_review("event-9", "mingau")

        self.assertEqual(len(learning.calibrations), 1)
        self.assertEqual(learning.calibrations[0]["interaction_count"], 10)
        self.assertEqual(learning.calibrations[0]["accuracy"], 1.0)

    def test_combines_multiple_observations_by_median(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_image(root / "mingau.jpg", (15, 35, 185))
            self.write_image(root / "luna.jpg", (180, 35, 15))
            repository = FakePetRepository([
                {"id": "mingau", "species": "CAT", "photo_path": "mingau.jpg"},
                {"id": "luna", "species": "CAT", "photo_path": "luna.jpg"},
            ])
            observations = [np.full((120, 120, 3), (15, 35, 185), dtype=np.uint8) for _ in range(3)]

            analysis = PetIdentifier(repository, FakeImageStore(root)).analyze_images(observations, "CAT")

            self.assertIsNotNone(analysis.match)
            self.assertEqual(analysis.match.pet_id, "mingau")
            self.assertEqual(analysis.method, PetIdentifier.METHOD)

    def test_selects_more_than_eight_reference_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            references = []
            for index in range(12):
                path = f"ref-{index}.jpg"
                self.write_image(root / path, (20 + index, 40, 160))
                references.append({"image_path": path})
            repository = FakePetRepository(
                [{"id": "mingau", "species": "CAT", "photo_path": None}],
                {"mingau": references},
            )
            identifier = PetIdentifier(repository, FakeImageStore(root))

            self.assertEqual(len(identifier._reference_descriptors(repository.pets[0])), 12)


if __name__ == "__main__":
    unittest.main()
