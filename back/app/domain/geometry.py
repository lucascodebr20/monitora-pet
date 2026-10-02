from app.domain.errors import InvalidDomainValueError


def validate_polygon(points: list[tuple[float, float]]) -> None:
    if len(set(points)) < 3:
        raise InvalidDomainValueError("A zona precisa de pelo menos três pontos distintos.")
    area = 0.0
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        area += current[0] * following[1] - following[0] * current[1]
    if abs(area) / 2 < 0.0001:
        raise InvalidDomainValueError("Os pontos da zona não formam uma área válida.")


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def polygon_area(polygon: list[tuple[float, float]]) -> float:
    area = 0.0
    for index, current in enumerate(polygon):
        following = polygon[(index + 1) % len(polygon)]
        area += current[0] * following[1] - following[0] * current[1]
    return abs(area) / 2


def polygon_rectangle_overlap_ratio(
    polygon: list[tuple[float, float]],
    rectangle: tuple[float, float, float, float],
) -> float:
    x1, y1, x2, y2 = rectangle
    clipped = polygon
    boundaries = (
        (lambda point: point[0] >= x1, lambda start, end: _vertical_intersection(start, end, x1)),
        (lambda point: point[0] <= x2, lambda start, end: _vertical_intersection(start, end, x2)),
        (lambda point: point[1] >= y1, lambda start, end: _horizontal_intersection(start, end, y1)),
        (lambda point: point[1] <= y2, lambda start, end: _horizontal_intersection(start, end, y2)),
    )
    for inside, intersection in boundaries:
        clipped = _clip_polygon(clipped, inside, intersection)
        if not clipped:
            return 0.0
    overlap_area = polygon_area(clipped)
    reference_area = min(polygon_area(polygon), max(0.0, x2 - x1) * max(0.0, y2 - y1))
    return overlap_area / reference_area if reference_area else 0.0


def _clip_polygon(polygon, inside, intersection):
    if not polygon:
        return []
    result = []
    previous = polygon[-1]
    previous_inside = inside(previous)
    for current in polygon:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside:
                result.append(intersection(previous, current))
            result.append(current)
        elif previous_inside:
            result.append(intersection(previous, current))
        previous = current
        previous_inside = current_inside
    return result


def _vertical_intersection(start, end, x):
    distance = end[0] - start[0]
    ratio = (x - start[0]) / distance if distance else 0.0
    return x, start[1] + (end[1] - start[1]) * ratio


def _horizontal_intersection(start, end, y):
    distance = end[1] - start[1]
    ratio = (y - start[1]) / distance if distance else 0.0
    return start[0] + (end[0] - start[0]) * ratio, y
