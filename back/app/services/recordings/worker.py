from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.domain.errors import DomainError
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.recording_repository import RecordingRepository
from app.services.recordings.analyzer import RecordingAnalyzer
from app.services.recordings.camera_sync import CameraRecordingSync
from app.services.recordings.importer import RecordingImportService

logger = logging.getLogger(__name__)

STATUS_IDLE = "idle"
STATUS_RUNNING = "running"


@dataclass(frozen=True)
class Job:
    kind: str
    camera_id: str | None = None


class ImportWorker:
    def __init__(
        self,
        importer: RecordingImportService,
        analyzer: RecordingAnalyzer | None,
        sync: CameraRecordingSync,
        recording_repository: RecordingRepository,
        camera_repository: CameraRepository,
        on_state: Callable[[str], None] | None = None,
    ) -> None:
        self.importer = importer
        self.analyzer = analyzer
        self.sync = sync
        self.recording_repository = recording_repository
        self.camera_repository = camera_repository
        self.on_state = on_state
        self._queue: deque[Job] = deque()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._idle = threading.Event()
        self._idle.set()
        self._stop_all = threading.Event()
        self._cancel_current = threading.Event()
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {
            "status": STATUS_IDLE,
            "stage": None,
            "camera_id": None,
            "camera_name": None,
            "recording_id": None,
            "progress_seconds": 0.0,
            "total_seconds": 0.0,
            "queue": 0,
            "pending_recordings": 0,
            "started_at": None,
            "finished_at": None,
            "last_result": None,
            "error": None,
        }

    def start(self) -> None:
        for recording in self.recording_repository.list(status="PROCESSING"):
            self.recording_repository.set_status(recording["id"], "PENDING")
        self._stop_all.clear()
        self._thread = threading.Thread(target=self._run, name="recording-worker", daemon=True)
        self._thread.start()
        if self.recording_repository.list(status="PENDING") or (self.importer.folders and self.importer.folders.list()):
            self.request_import()

    def stop(self) -> None:
        self._stop_all.set()
        self._cancel_current.set()
        self._wake.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._thread = None

    def request_import(self, camera_id: str | None = None) -> dict[str, Any]:
        return self._enqueue(Job("import", camera_id))

    def request_sync(self, camera_id: str) -> dict[str, Any]:
        self._enqueue(Job("sync", camera_id))
        return self._enqueue(Job("import", camera_id))

    def cancel(self) -> dict[str, Any]:
        with self._lock:
            self._queue.clear()
        self._cancel_current.set()
        return self.state()

    def wait_idle(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    def state(self) -> dict[str, Any]:
        with self._lock:
            snapshot = dict(self._state)
            snapshot["queue"] = len(self._queue)
        snapshot["pending_recordings"] = len(self.recording_repository.list(status="PENDING"))
        return snapshot

    def run_pending(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    return
                job = self._queue.popleft()
            self._process(job)

    def _enqueue(self, job: Job) -> dict[str, Any]:
        with self._lock:
            if job not in self._queue:
                self._queue.append(job)
        self._idle.clear()
        self._wake.set()
        return self.state()

    def _run(self) -> None:
        while not self._stop_all.is_set():
            self._wake.wait()
            self._wake.clear()
            if self._stop_all.is_set():
                break
            self._set_status(STATUS_RUNNING)
            try:
                self.run_pending()
            finally:
                self._set_status(STATUS_IDLE)
                self._idle.set()

    def _process(self, job: Job) -> None:
        self._cancel_current.clear()
        camera = self.camera_repository.get(job.camera_id) if job.camera_id else None
        self._update(
            stage="downloading" if job.kind == "sync" else "scanning",
            camera_id=job.camera_id,
            camera_name=camera["name"] if camera else None,
            recording_id=None,
            progress_seconds=0.0,
            total_seconds=0.0,
            started_at=self._now(),
            finished_at=None,
            error=None,
        )
        try:
            if job.kind == "sync" and job.camera_id:
                result = self.sync.sync(job.camera_id)
                self._update(last_result={"kind": "sync", "downloaded": len(result.downloaded), "errors": result.errors})
            else:
                self._import(job.camera_id)
        except DomainError as error:
            self._update(error=str(error))
        except Exception as error:
            logger.exception("Falha no trabalho %s da câmera %s", job.kind, job.camera_id)
            self._update(error=str(error))
        finally:
            self._update(stage=None, recording_id=None, finished_at=self._now())

    def _import(self, camera_id: str | None) -> None:
        self.importer.scan_watched_folders(camera_id)
        if self.analyzer is None:
            self._update(error="Modelo de IA ausente; as gravações ficam na fila até o modelo estar disponível.")
            return
        camera_ids = [camera_id] if camera_id else self.recording_repository.pending_camera_ids()
        totals = {"processed": 0, "skipped": 0, "failed": 0, "events_before": 0}
        for current in camera_ids:
            if self._cancel_current.is_set():
                break
            pending = self.recording_repository.list(current, "PENDING")
            if not pending:
                continue
            camera = self.camera_repository.get(current)
            self._update(stage="analyzing", camera_id=current, camera_name=camera["name"] if camera else None)
            result = self.analyzer.analyze_camera(
                current, pending, should_stop=self._cancel_current.is_set, on_progress=self._on_progress
            )
            totals["processed"] += result.processed
            totals["skipped"] += result.skipped
            totals["failed"] += result.failed
            if result.interrupted:
                break
        self._update(last_result={"kind": "import", **totals})

    def _on_progress(self, recording_id: str, offset: float) -> None:
        recording = self.recording_repository.get(recording_id)
        total = 0.0
        if recording:
            total = (
                datetime.fromisoformat(recording["ended_at"]) - datetime.fromisoformat(recording["started_at"])
            ).total_seconds()
        self._update(recording_id=recording_id, progress_seconds=offset, total_seconds=total)

    def _set_status(self, status: str) -> None:
        with self._lock:
            changed = self._state["status"] != status
            self._state["status"] = status
        if changed and self.on_state:
            try:
                self.on_state(status)
            except Exception:
                logger.exception("Falha ao notificar o estado do trabalho")

    def _update(self, **values: Any) -> None:
        with self._lock:
            self._state.update(values)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
