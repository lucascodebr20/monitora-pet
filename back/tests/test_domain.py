import unittest

from app.domain.errors import InvalidDomainValueError
from app.domain.geometry import validate_polygon


class GeometryTests(unittest.TestCase):
    def test_accepts_polygon_with_area(self):
        validate_polygon([(0.1, 0.1), (0.8, 0.1), (0.8, 0.8)])

    def test_rejects_collinear_polygon(self):
        with self.assertRaises(InvalidDomainValueError):
            validate_polygon([(0.1, 0.1), (0.2, 0.2), (0.3, 0.3)])

    def test_rejects_repeated_points(self):
        with self.assertRaises(InvalidDomainValueError):
            validate_polygon([(0.1, 0.1), (0.1, 0.1), (0.8, 0.8)])


if __name__ == "__main__":
    unittest.main()
