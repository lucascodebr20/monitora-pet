import unittest

from app.domain.errors import InvalidDomainValueError
from app.domain.geometry import polygon_rectangle_overlap_ratio, validate_polygon


class GeometryTests(unittest.TestCase):
    def test_accepts_polygon_with_area(self):
        validate_polygon([(0.1, 0.1), (0.8, 0.1), (0.8, 0.8)])

    def test_rejects_collinear_polygon(self):
        with self.assertRaises(InvalidDomainValueError):
            validate_polygon([(0.1, 0.1), (0.2, 0.2), (0.3, 0.3)])

    def test_rejects_repeated_points(self):
        with self.assertRaises(InvalidDomainValueError):
            validate_polygon([(0.1, 0.1), (0.1, 0.1), (0.8, 0.8)])

    def test_measures_polygon_and_detection_overlap(self):
        zone = [(0.55, 0.3), (0.8, 0.3), (0.8, 0.75), (0.55, 0.75)]

        ratio = polygon_rectangle_overlap_ratio(zone, (0.7, 0.2, 0.98, 0.8))

        self.assertGreater(ratio, 0.35)

    def test_returns_zero_for_separate_areas(self):
        zone = [(0.1, 0.1), (0.3, 0.1), (0.3, 0.3), (0.1, 0.3)]

        ratio = polygon_rectangle_overlap_ratio(zone, (0.7, 0.7, 0.9, 0.9))

        self.assertEqual(ratio, 0.0)


if __name__ == "__main__":
    unittest.main()
