from __future__ import annotations

import sqlite3
from dataclasses import asdict
from typing import Any, Iterator

from app.domain.errors import EntityConflictError, EntityNotFoundError, OperationFailedError
from app.infra.camera.discovery import discover_all, fallback_scan
from app.infra.camera.manager import CameraManager
from app.infra.camera.onvif import device_information, stream_urls
from app.infra.camera.stream import CameraConnectionError, authenticate_urls, candidate_urls, split_url_credentials
from app.infra.repositories.camera_repository import CameraRepository
from app.services.commands import CameraCredentialsCommand, CreateCameraCommand


class CameraService:
    def __init__(self, repository: CameraRepository, manager: CameraManager) -> None:
        self.repository = repository
        self.manager = manager

    def discover(self, fallback: bool = False) -> list[dict[str, object]]:
        devices = fallback_scan() if fallback else discover_all()
        registered_ips = {str(camera["ip"]) for camera in self.repository.list()}
        return [device for device in devices if str(device.get("ip", "")) not in registered_ips]

    def list(self) -> list[dict[str, Any]]:
        return [self._view(camera) for camera in self.repository.list()]

    def create(self, request: CreateCameraCommand) -> dict[str, Any]:
        identity = device_information(request.ip, request.onvif_port, request.username, request.password)
        values = asdict(request)
        values.pop("username")
        values.pop("password")
        values.update(identity)
        try:
            camera = self.repository.create(values)
        except sqlite3.IntegrityError as exc:
            raise EntityConflictError("Já existe uma câmera cadastrada com esse IP.") from exc
        credentials = CameraCredentialsCommand(
            username=request.username, password=request.password, rtsp_url=request.rtsp_url
        )
        try:
            self.manager.connect(camera["id"], self._connection_urls(camera, credentials))
        except (CameraConnectionError, ValueError):
            pass
        return self._view(camera)

    def connect(self, camera_id: str, credentials: CameraCredentialsCommand) -> dict[str, Any]:
        camera = self.get(camera_id)
        try:
            self.manager.connect(camera_id, self._connection_urls(camera, credentials))
        except (CameraConnectionError, ValueError) as exc:
            raise OperationFailedError(str(exc)) from exc
        return self.manager.status(camera_id)

    def disconnect(self, camera_id: str) -> dict[str, Any]:
        self.get(camera_id)
        self.manager.disconnect(camera_id)
        return self.manager.status(camera_id)

    def delete(self, camera_id: str) -> None:
        self.get(camera_id)
        self.manager.disconnect(camera_id)
        self.repository.delete(camera_id)

    def frames(self, camera_id: str) -> Iterator[bytes]:
        self.get(camera_id)
        try:
            return self.manager.frames(camera_id)
        except KeyError as exc:
            raise OperationFailedError("A câmera não está conectada.") from exc

    def get(self, camera_id: str) -> dict[str, Any]:
        camera = self.repository.get(camera_id)
        if not camera:
            raise EntityNotFoundError("Câmera não encontrada.")
        return camera

    def health(self) -> dict[str, int]:
        registered = self.repository.list()
        connected = sum(bool(self.manager.status(item["id"])["connected"]) for item in registered)
        return {"registered": len(registered), "connected": connected}

    def _view(self, camera: dict[str, Any]) -> dict[str, Any]:
        result = dict(camera)
        result["enabled"] = bool(result["enabled"])
        result.pop("credential_ref", None)
        if result.get("rtsp_url"):
            result["rtsp_url"] = split_url_credentials(result["rtsp_url"])[0]
        result["status"] = self.manager.status(str(result["id"]))
        return result

    def _connection_urls(self, camera: dict[str, Any], credentials: CameraCredentialsCommand) -> list[str]:
        rtsp_url = credentials.rtsp_url or camera.get("rtsp_url")
        if rtsp_url:
            return candidate_urls(camera["ip"], credentials.username, credentials.password, rtsp_url)
        announced = stream_urls(
            camera["ip"], camera["onvif_port"], credentials.username, credentials.password
        )
        urls = authenticate_urls(announced, credentials.username, credentials.password)
        urls.extend(candidate_urls(camera["ip"], credentials.username, credentials.password, None))
        return list(dict.fromkeys(urls))
