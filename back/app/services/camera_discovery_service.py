from __future__ import annotations

from app.infra.camera.discovery import discover_all, fallback_scan
from app.infra.repositories.camera_repository import CameraRepository


class CameraDiscoveryService:
    def __init__(self, repository: CameraRepository) -> None:
        self.repository = repository

    def discover(self, fallback: bool = False) -> list[dict[str, object]]:
        devices = fallback_scan() if fallback else discover_all()
        registered_ips = {str(camera["ip"]) for camera in self.repository.list()}
        return [device for device in devices if str(device.get("ip", "")) not in registered_ips]
