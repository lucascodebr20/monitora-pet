from __future__ import annotations

import logging
from typing import Any, Callable

from app.infra.camera import onvif
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.security.credential_store import CredentialStore

logger = logging.getLogger(__name__)

SUPPORT_UNKNOWN = "UNKNOWN"
SUPPORT_NONE = "NONE"
SUPPORT_ONVIF_REPLAY = "ONVIF_REPLAY"
MAX_TRUSTED_OFFSET_SECONDS = 15 * 60


class CameraProfileService:
    def __init__(
        self,
        repository: CameraRepository,
        credentials: CredentialStore,
        recording_services: Callable[..., dict[str, str]] = onvif.recording_services,
        clock_offset: Callable[..., float | None] = onvif.device_clock_offset,
    ) -> None:
        self.repository = repository
        self.credentials = credentials
        self._recording_services = recording_services
        self._clock_offset = clock_offset

    def remember(self, camera_id: str, username: str, password: str) -> None:
        if username or password:
            self.credentials.save(camera_id, username, password)

    def credentials_for(self, camera_id: str) -> tuple[str, str]:
        return self.credentials.get(camera_id) or ("", "")

    def forget(self, camera_id: str) -> None:
        self.credentials.delete(camera_id)

    def probe(self, camera: dict[str, Any]) -> dict[str, Any]:
        if camera.get("source_kind") == "MANUAL":
            return {"recording_support": SUPPORT_NONE, "clock_offset_seconds": 0.0, "clock_warning": False}
        username, password = self.credentials_for(camera["id"])
        services = self._recording_services(camera["ip"], camera["onvif_port"], username, password)
        offset = self._clock_offset(camera["ip"], camera["onvif_port"], username, password)
        support = SUPPORT_ONVIF_REPLAY if services else SUPPORT_NONE
        self.repository.update_recording_profile(camera["id"], support, offset)
        warning = offset is not None and abs(offset) > MAX_TRUSTED_OFFSET_SECONDS
        if warning:
            logger.warning("Relógio da câmera %s difere do PC em %.0f s", camera["id"], offset)
        return {"recording_support": support, "clock_offset_seconds": offset or 0.0, "clock_warning": warning}
