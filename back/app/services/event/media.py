from __future__ import annotations

from pathlib import Path

from app.domain.errors import EntityNotFoundError
from app.infra.media.clip_store import ClipStore
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.event_repository import EventRepository


class EventMediaService:
    def __init__(self, repository: EventRepository, snapshot_store: SnapshotStore, clip_store: ClipStore) -> None:
        self.repository = repository
        self.snapshot_store = snapshot_store
        self.clip_store = clip_store

    def snapshot(self, event_id: str) -> Path:
        event = self._event(event_id)
        if not event.get("snapshot_path"):
            raise EntityNotFoundError("Este evento não possui snapshot.")
        path = self.snapshot_store.resolve(event["snapshot_path"])
        if not path.is_file():
            raise EntityNotFoundError("O snapshot deste evento não está mais disponível.")
        return path

    def clip(self, event_id: str) -> Path:
        event = self._event(event_id)
        if not event.get("clip_path"):
            raise EntityNotFoundError("Este evento ainda não possui vídeo.")
        path = self.clip_store.resolve(event["clip_path"])
        if not path.is_file():
            raise EntityNotFoundError("O vídeo deste evento não está mais disponível.")
        return path

    def _event(self, event_id: str) -> dict:
        event = self.repository.get(event_id)
        if not event:
            raise EntityNotFoundError("Evento não encontrado.")
        return event
