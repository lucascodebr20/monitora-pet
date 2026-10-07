from __future__ import annotations

from pathlib import Path

from app.infra.media.media_cleanup import MediaCleanup
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.recording_repository import RecordingRepository


class EventPurgeService:
    def __init__(
        self,
        event_repository: EventRepository,
        recording_repository: RecordingRepository,
        cleanup: MediaCleanup,
    ) -> None:
        self.event_repository = event_repository
        self.recording_repository = recording_repository
        self.cleanup = cleanup

    def purge_recording(self, recording_id: str) -> int:
        return self.cleanup.remove(self.event_repository.delete_by_recording(recording_id))

    def purge_zone(self, zone_id: str) -> int:
        return self.cleanup.remove(self.event_repository.delete_by_zone(zone_id))

    def purge_camera(self, camera_id: str) -> int:
        removed = self.cleanup.remove(self.event_repository.delete_by_camera(camera_id))
        for recording in self.recording_repository.list(camera_id):
            if self.cleanup.owns(recording["path"]):
                removed += self.cleanup.remove([Path(recording["path"])])
        return removed
