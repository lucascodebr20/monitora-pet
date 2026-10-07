from __future__ import annotations

import logging
from dataclasses import asdict
from uuid import uuid4
from typing import Any, Iterator

from app.domain.errors import EntityNotFoundError, InvalidDomainValueError, OperationFailedError
from app.domain.urls import split_url_credentials
from app.infra.camera.connection import resolve_connection_urls
from app.infra.camera.manager import CameraManager
from app.infra.camera.onvif import device_information
from app.infra.camera.stream import CameraConnectionError
from app.infra.repositories.camera_repository import CameraRepository
from app.services.camera.commands import CameraCredentialsCommand, ConvertCameraCommand, CreateCameraCommand
from app.services.camera.profile import CameraProfileService
from app.services.event.purge import EventPurgeService

logger = logging.getLogger(__name__)


class CameraService:
    def __init__(
        self,
        repository: CameraRepository,
        manager: CameraManager,
        purge: EventPurgeService | None = None,
        profile: CameraProfileService | None = None,
    ) -> None:
        self.repository = repository
        self.manager = manager
        self.purge = purge
        self.profile = profile

    def list(self) -> list[dict[str, Any]]:
        return [self._view(camera) for camera in self.repository.list()]

    def get(self, camera_id: str) -> dict[str, Any]:
        camera = self.repository.get(camera_id)
        if not camera:
            raise EntityNotFoundError("Câmera não encontrada.")
        return camera

    def create(self, request: CreateCameraCommand) -> dict[str, Any]:
        try:
            urls = resolve_connection_urls(
                request.ip, request.onvif_port, request.rtsp_url, request.username, request.password
            )
        except ValueError as exc:
            raise InvalidDomainValueError(str(exc)) from exc
        identity = device_information(request.ip, request.onvif_port, request.username, request.password)
        values = asdict(request)
        values.pop("username")
        values.pop("password")
        values.update(identity)
        camera = self.repository.create(values)
        self._remember(camera, request.username, request.password)
        try:
            self.manager.connect(camera["id"], urls)
            logger.info("Câmera %s (%s) cadastrada e conectada", camera["id"], request.ip)
        except CameraConnectionError as exc:
            logger.warning("Câmera %s (%s) cadastrada sem conexão: %s", camera["id"], request.ip, exc)
        return self._view(self.repository.get(camera["id"]) or camera)

    def create_manual(self, name: str) -> dict[str, Any]:
        camera = self.repository.create({
            "name": name,
            "ip": f"manual-{uuid4().hex[:8]}",
            "source_kind": "MANUAL",
        })
        self.repository.update_recording_profile(camera["id"], "NONE", 0.0)
        return self._view(self.repository.get(camera["id"]) or camera)

    def convert_to_network(self, camera_id: str, request: ConvertCameraCommand) -> dict[str, Any]:
        camera = self.get(camera_id)
        if camera.get("source_kind") != "MANUAL":
            raise InvalidDomainValueError("Esta câmera já está configurada pela rede.")
        try:
            urls = resolve_connection_urls(
                request.ip, request.onvif_port, request.rtsp_url, request.username, request.password
            )
        except ValueError as exc:
            raise InvalidDomainValueError(str(exc)) from exc
        self.repository.convert_to_network(camera_id, request.ip, request.onvif_port, request.rtsp_url)
        converted = self.repository.get(camera_id) or camera
        self._remember(converted, request.username, request.password)
        try:
            self.manager.connect(camera_id, urls)
        except CameraConnectionError as exc:
            logger.warning("Câmera %s convertida sem conexão: %s", camera_id, exc)
        return self._view(self.repository.get(camera_id) or converted)

    def connect(self, camera_id: str, credentials: CameraCredentialsCommand) -> dict[str, Any]:
        camera = self.get(camera_id)
        if camera.get("source_kind") == "MANUAL":
            raise InvalidDomainValueError("Câmeras manuais recebem gravações por pasta, não por conexão de rede.")
        try:
            urls = resolve_connection_urls(
                camera["ip"],
                camera["onvif_port"],
                credentials.rtsp_url or camera.get("rtsp_url"),
                credentials.username,
                credentials.password,
            )
            self.manager.connect(camera_id, urls)
        except (CameraConnectionError, ValueError) as exc:
            raise OperationFailedError(str(exc)) from exc
        self._remember(camera, credentials.username, credentials.password)
        return self.manager.status(camera_id)

    def reconnect_all(self) -> None:
        if not self.profile:
            return
        for camera in self.repository.list():
            if camera.get("source_kind") == "MANUAL":
                continue
            username, password = self.profile.credentials_for(camera["id"])
            if not username and not password:
                continue
            try:
                urls = resolve_connection_urls(camera["ip"], camera["onvif_port"], camera.get("rtsp_url"), username, password)
                self.manager.connect(camera["id"], urls)
                logger.info("Câmera %s reconectada com as credenciais salvas", camera["id"])
            except (CameraConnectionError, ValueError) as exc:
                logger.warning("Câmera %s não reconectou no início: %s", camera["id"], exc)

    def disconnect(self, camera_id: str) -> dict[str, Any]:
        self.get(camera_id)
        self.manager.disconnect(camera_id)
        return self.manager.status(camera_id)

    def delete(self, camera_id: str) -> None:
        self.get(camera_id)
        self.manager.disconnect(camera_id)
        if self.purge:
            self.purge.purge_camera(camera_id)
        if self.profile:
            self.profile.forget(camera_id)
        self.repository.delete(camera_id)

    def frames(self, camera_id: str) -> Iterator[bytes]:
        self.get(camera_id)
        try:
            return self.manager.frames(camera_id)
        except KeyError as exc:
            raise OperationFailedError("A câmera não está conectada.") from exc

    def health(self) -> dict[str, int]:
        registered = self.repository.list()
        connected = sum(bool(self.manager.status(item["id"])["connected"]) for item in registered)
        return {"registered": len(registered), "connected": connected}

    def _remember(self, camera: dict[str, Any], username: str, password: str) -> None:
        if not self.profile:
            return
        self.profile.remember(camera["id"], username, password)
        try:
            self.profile.probe(camera)
        except Exception:
            logger.exception("Falha ao sondar suporte a gravações da câmera %s", camera["id"])

    def _view(self, camera: dict[str, Any]) -> dict[str, Any]:
        result = dict(camera)
        result["enabled"] = bool(result["enabled"])
        result.pop("credential_ref", None)
        if result.get("source_kind") == "MANUAL":
            result["ip"] = ""
        if result.get("rtsp_url"):
            result["rtsp_url"] = split_url_credentials(result["rtsp_url"])[0]
        result["status"] = self.manager.status(str(result["id"]))
        return result
