from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

FILENAME = "credentials.bin"
PREFIX_DPAPI = b"DPAPI1:"
PREFIX_PLAIN = b"PLAIN1:"


class CredentialStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / FILENAME
        self._lock = Lock()

    def save(self, camera_id: str, username: str, password: str) -> None:
        with self._lock:
            entries = self._read()
            entries[camera_id] = {"username": username, "password": password}
            self._write(entries)

    def get(self, camera_id: str) -> tuple[str, str] | None:
        with self._lock:
            entry = self._read().get(camera_id)
        if not entry:
            return None
        return entry.get("username", ""), entry.get("password", "")

    def delete(self, camera_id: str) -> None:
        with self._lock:
            entries = self._read()
            if entries.pop(camera_id, None) is not None:
                self._write(entries)

    def _read(self) -> dict[str, dict[str, str]]:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(_unprotect(self.path.read_bytes()).decode("utf-8"))
        except (OSError, ValueError) as error:
            logger.warning("Não foi possível ler as credenciais salvas: %s", error)
            return {}

    def _write(self, entries: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = _protect(json.dumps(entries).encode("utf-8"))
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(payload)
        if sys.platform != "win32":
            os.chmod(temporary, 0o600)
        temporary.replace(self.path)


def _protect(data: bytes) -> bytes:
    if sys.platform == "win32":
        return PREFIX_DPAPI + base64.b64encode(_dpapi(data, encrypt=True))
    logger.warning("Credenciais de câmera gravadas sem cifra nesta plataforma; proteja a pasta de dados.")
    return PREFIX_PLAIN + base64.b64encode(data)


def _unprotect(payload: bytes) -> bytes:
    if payload.startswith(PREFIX_DPAPI):
        return _dpapi(base64.b64decode(payload[len(PREFIX_DPAPI):]), encrypt=False)
    if payload.startswith(PREFIX_PLAIN):
        return base64.b64decode(payload[len(PREFIX_PLAIN):])
    raise ValueError("Formato de credenciais desconhecido.")


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = DataBlob()
    function = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    if not function(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise ValueError("Falha ao proteger as credenciais com o Windows.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)
