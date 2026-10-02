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
