from __future__ import annotations

from app.domain.detection import Detection
from app.domain.geometry import point_in_polygon, polygon_rectangle_overlap_ratio

Polygon = list[tuple[float, float]]

MINIMUM_ZONE_OVERLAP = 0.2


def detection_zone_score(detection: Detection, polygon: Polygon) -> float:
    rectangle = detection.x1, detection.y1, detection.x2, detection.y2
    overlap = polygon_rectangle_overlap_ratio(polygon, rectangle)
    if point_in_polygon(detection.centroid, polygon):
        return max(1.0, overlap)
    return overlap


def detection_in_zone(detection: Detection, polygon: Polygon) -> bool:
    return detection_zone_score(detection, polygon) >= MINIMUM_ZONE_OVERLAP


def assign_detections(polygons: dict[str, Polygon], detections: list[Detection]) -> dict[str, list[Detection]]:
    assigned: dict[str, list[Detection]] = {zone_id: [] for zone_id in polygons}
    for detection in detections:
        candidates: list[tuple[float, float, str]] = []
        for zone_id, polygon in polygons.items():
            score = detection_zone_score(detection, polygon)
            if score < MINIMUM_ZONE_OVERLAP:
                continue
            center_x = sum(point[0] for point in polygon) / len(polygon)
            center_y = sum(point[1] for point in polygon) / len(polygon)
            distance = (detection.centroid[0] - center_x) ** 2 + (detection.centroid[1] - center_y) ** 2
            candidates.append((score, -distance, zone_id))
        if candidates:
            assigned[max(candidates)[2]].append(detection)
    return assigned
