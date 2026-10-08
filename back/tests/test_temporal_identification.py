import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from app.domain.clock import Moment
from app.domain.detection import Detection
from app.domain.enums import PetSpecies, ReviewDecision
from app.infra.ai.pet_identifier import PetAnalysis, PetIdentifier, PetMatch
from app.infra.database.database import Database
from app.infra.media.pet_image_store import PetImageStore
from app.infra.repositories.pet_repository import PetRepository
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.services.event import EventReviewService, ReviewEventCommand
from app.services.monitoring.events import EventRecorder
from app.services.monitoring.observations import MAX_CAPTURE_EDGE, MAX_PET_OBSERVATIONS, PetObservations
from app.services.monitoring.tracking import ZoneTracker
from app.services.monitoring.clips import ClipRecorder
from tests.test_monitoring import FakeSnapshotStore, FakeClipStore, FrameSnapshotSource, build_repositories, square_zone

EPOCH = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def image(offset=0, edge=200):
    texture = np.random.default_rng(42).integers(0, 100, (edge, edge, 3), dtype=np.uint8)
    return (texture.astype(np.uint16) + offset).clip(0, 255).astype(np.uint8)


class ObservationTests(unittest.TestCase):
    def test_samples_are_bounded_and_repeated_frames_do_not_dominate(self):
        pool = PetObservations()
        for index in range(100):
            pool.add(image(80, 400), index)
        self.assertEqual(len(pool.images), 1)
        self.assertLessEqual(max(pool.images[0].shape[:2]), MAX_CAPTURE_EDGE)
        for index in range(14):
            pool.add(image(index * 11, 400), 200 + index)
        self.assertLessEqual(len(pool.images), MAX_PET_OBSERVATIONS)
        self.assertGreater(len(pool.images), 1)
        self.assertLessEqual(sum(item.nbytes for item in pool.images), MAX_PET_OBSERVATIONS * MAX_CAPTURE_EDGE ** 2 * 3)

    def test_better_frames_replace_blurred_fallback_and_sampling_is_spaced(self):
        pool = PetObservations()
        blurred = np.full((200, 200, 3), 120, dtype=np.uint8)
        pool.add(blurred, 0)
        pool.add(image(80), 0.1)
        self.assertEqual(len(pool.images), 1)
        self.assertTrue(np.array_equal(pool.images[0], blurred))
        pool.add(image(80), 1)
        self.assertEqual(len(pool.images), 1)
        self.assertGreater(PetIdentifier.image_quality(pool.images[0]), PetIdentifier.image_quality(blurred))

    def test_inconsistent_frames_do_not_force_a_median_match(self):
        identifier = PetIdentifier.__new__(PetIdentifier)
        identifier.repository = Mock()
        identifier.repository.list_by_species.return_value = [{'id': 'tom'}, {'id': 'ciri'}]
        identifier._thresholds = Mock(return_value=(0.7, 0.0))
        identifier._descriptor = Mock(side_effect=lambda frame: int(frame[0, 0, 0]))
        identifier._reference_descriptors = Mock(side_effect=lambda pet: [pet['id']])
        identifier._gallery_score = Mock(side_effect=lambda value, references: (
            0.95 if (value < 2) == (references[0] == 'tom') else 0.8
        ))
        analysis = identifier.analyze_images([np.full((2, 2, 3), value, dtype=np.uint8) for value in range(4)], 'CAT')
        self.assertIsNone(analysis.match)
        self.assertEqual(analysis.decision, 'INCONSISTENT_OBSERVATIONS')


class TemporalIdentificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database, cameras, zones, self.events = build_repositories(self.root)
        self.camera = cameras.create({'name': 'Sala', 'ip': '192.168.1.10'})
        self.zone = zones.create(square_zone(self.camera['id'], 'Comida', 'FOOD', 1, cooldown=2, tolerance=0.5))
        self.pets = PetRepository(self.database)
        self.tom = self.pets.create('Tom', 'CAT', '', None)
        self.ciri = self.pets.create('Ciri', 'CAT', '', None)
        self.images = PetImageStore(self.root, self.root / 'pets')
        self.analyses = PetIdentificationRepository(self.database)
        self.identifier = Mock(spec=PetIdentifier)
        self.identifier.analyze_images.side_effect = lambda observations, species: self.analysis(self.tom if len(observations) < 3 else self.ciri)
        self.identifier.analyze.side_effect = lambda path, species: self.analysis(self.tom)
        self.identifier.record_analysis.side_effect = lambda event_id, path, species, analysis, count, stage: self.analyses.create_analysis(
            event_id, species, path, analysis.decision, analysis.match.pet_id if analysis.match else None,
            analysis.match.confidence if analysis.match else None, analysis.minimum_similarity, analysis.minimum_margin,
            list(analysis.scores), analysis.method, count, stage,
        )
        self.auto_review = Mock()
        self.auto_review.should_confirm.return_value = True
        snapshot = FakeSnapshotStore()
        recorder = EventRecorder(self.events, snapshot, FrameSnapshotSource(snapshot), self.images, self.identifier, auto_review=self.auto_review)
        self.tracker = ZoneTracker(ClipRecorder(FakeClipStore(), self.events), recorder, self.images)
        self.detection = Detection(0.3, 0.3, 0.7, 0.7, 0.95)

    def tearDown(self):
        self.temp.cleanup()

    def analysis(self, pet):
        return PetAnalysis(PetMatch(pet['id'], 0.95), 'MATCHED', ({'pet_id': pet['id'], 'confidence': 0.95, 'reference_count': 1},), 0.7, 0.05)

    def observe(self, seconds, offset=80, detections=None):
        return self.tracker.track(self.camera['id'], image(offset), [self.zone],
                                  [self.detection] if detections is None else detections,
                                  Moment(seconds, EPOCH + timedelta(seconds=seconds)))

    def finish(self):
        self.observe(4, detections=[])
        self.observe(6, detections=[])

    def test_final_refinement_uses_later_frames_and_defers_auto_review(self):
        self.observe(0, 50)
        self.observe(1, 70)
        event = self.events.list()[0]
        self.assertEqual(event['pet_id'], self.tom['id'])
        self.auto_review.confirm.assert_not_called()
        initial_path = event['pet_capture_path']
        self.observe(2, 90)
        self.observe(3, 110)
        self.finish()
        final = self.events.find(event['id'])
        self.assertEqual(final['pet_id'], self.ciri['id'])
        self.assertIsNotNone(final['ended_at'])
        row = self.database.one('SELECT * FROM pet_identification_analyses WHERE event_id = ?', (event['id'],))
        self.assertEqual(row['initial_selected_pet_id'], self.tom['id'])
        self.assertEqual(row['selected_pet_id'], self.ciri['id'])
        self.assertEqual(row['identification_stage'], 'FINAL')
        self.assertEqual(row['observation_count'], 4)
        self.assertEqual(self.database.one('SELECT COUNT(*) AS count FROM pet_identification_analyses')['count'], 1)
        self.assertFalse(self.images.resolve(initial_path).exists())
        self.assertTrue(self.images.resolve(final['pet_capture_path']).is_file())
        self.auto_review.confirm.assert_called_once_with(event['id'], self.ciri['id'])

    def test_second_pet_makes_visit_ambiguous_and_blocks_auto_review(self):
        self.observe(0)
        self.observe(1)
        event = self.events.list()[0]
        for seconds in (2, 2.5, 3):
            self.observe(seconds, detections=[self.detection, Detection(0.4, 0.4, 0.6, 0.6, 0.9)])
        self.finish()
        self.assertIsNone(self.events.find(event['id'])['pet_id'])
        row = self.database.one('SELECT * FROM pet_identification_analyses WHERE event_id = ?', (event['id'],))
        self.assertEqual(row['decision'], 'MULTIPLE_PETS')
        self.auto_review.confirm.assert_not_called()

    def test_single_frame_glitches_do_not_block_identification(self):
        self.observe(0, 50)
        self.observe(1, 70)
        event = self.events.list()[0]
        self.observe(2, 90, detections=[self.detection, Detection(0.35, 0.35, 0.65, 0.65, 0.5, PetSpecies.DOG)])
        self.observe(3, 110, detections=[Detection(0.3, 0.3, 0.7, 0.7, 0.9, PetSpecies.DOG)])
        self.finish()
        row = self.database.one('SELECT decision, selected_pet_id FROM pet_identification_analyses WHERE event_id = ?', (event['id'],))
        self.assertEqual(row['decision'], 'MATCHED')
        self.assertEqual(row['selected_pet_id'], self.ciri['id'])

    def test_jump_to_another_spot_marks_track_unstable(self):
        self.observe(0)
        self.observe(1)
        event = self.events.list()[0]
        self.observe(2, detections=[Detection(0.15, 0.15, 0.29, 0.29, 0.9)])
        self.finish()
        self.assertIsNone(self.events.find(event['id'])['pet_id'])
        row = self.database.one('SELECT decision FROM pet_identification_analyses WHERE event_id = ?', (event['id'],))
        self.assertEqual(row['decision'], 'UNSTABLE_TRACK')

    def test_human_review_and_its_reference_image_are_never_overwritten(self):
        self.observe(0, 50)
        self.observe(1, 70)
        event = self.events.list()[0]
        EventReviewService(self.events, self.pets).review(event['id'], ReviewEventCommand(
            decision=ReviewDecision.NO_ACTION, corrected_activity=None, pet_id=self.tom['id'], notes=None,
        ))
        self.observe(2, 90)
        self.observe(3, 110)
        self.finish()
        final = self.events.find(event['id'])
        self.assertEqual(final['pet_id'], self.tom['id'])
        self.assertEqual(final['pet_capture_path'], event['pet_capture_path'])
        self.assertEqual(final['review_decision'], 'NO_ACTION')
        self.assertTrue(self.images.resolve(final['pet_capture_path']).exists())
        self.auto_review.confirm.assert_not_called()
