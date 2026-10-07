from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

ONVIF_REPLAY_EXTENSION = 0xABAC
NTP_EPOCH = datetime(1900, 1, 1, tzinfo=timezone.utc)
READ_TIMEOUT_SECONDS = 20.0
START_CODE = b"\x00\x00\x00\x01"
H264_FU_A = 28
H264_STAP_A = 24
HEVC_AP = 48
HEVC_FU = 49


class ReplayError(RuntimeError):
    pass


@dataclass
class ReplayResult:
    path: Path
    codec: str
    frames: int
    first_timestamp: datetime | None
    last_timestamp: datetime | None


@dataclass
class _Track:
    control: str
    codec: str
    payload_type: int
    parameter_sets: list[bytes] = field(default_factory=list)


class _Depacketizer:
    def __init__(self, codec: str) -> None:
        self.codec = codec
        self._fragment = bytearray()

    def units(self, payload: bytes) -> list[bytes]:
        if not payload:
            return []
        return self._hevc(payload) if self.codec == "h265" else self._h264(payload)

    def _h264(self, payload: bytes) -> list[bytes]:
        kind = payload[0] & 0x1F
        if kind == H264_STAP_A:
            return list(_aggregated(payload, 1))
        if kind == H264_FU_A:
            if len(payload) < 2:
                return []
            indicator, header = payload[0], payload[1]
            if header & 0x80:
                self._fragment = bytearray([(indicator & 0xE0) | (header & 0x1F)])
            self._fragment += payload[2:]
            if header & 0x40:
                unit, self._fragment = bytes(self._fragment), bytearray()
                return [unit]
            return []
        return [payload]

    def _hevc(self, payload: bytes) -> list[bytes]:
        if len(payload) < 2:
            return []
        kind = (payload[0] >> 1) & 0x3F
        if kind == HEVC_AP:
            return list(_aggregated(payload, 2))
        if kind == HEVC_FU:
            if len(payload) < 3:
                return []
            fu_header = payload[2]
            if fu_header & 0x80:
                nal_type = fu_header & 0x3F
                self._fragment = bytearray([(payload[0] & 0x81) | (nal_type << 1), payload[1]])
            self._fragment += payload[3:]
            if fu_header & 0x40:
                unit, self._fragment = bytes(self._fragment), bytearray()
                return [unit]
            return []
        return [payload]


def _aggregated(payload: bytes, header_size: int):
    offset = header_size
    while offset + 2 <= len(payload):
        size = int.from_bytes(payload[offset:offset + 2], "big")
        offset += 2
        if size == 0 or offset + size > len(payload):
            return
        yield payload[offset:offset + size]
        offset += size


def parse_rtp(packet: bytes) -> tuple[bool, int, datetime | None, bytes] | None:
    if len(packet) < 12 or packet[0] >> 6 != 2:
        return None
    has_padding = bool(packet[0] & 0x20)
    has_extension = bool(packet[0] & 0x10)
    csrc_count = packet[0] & 0x0F
    marker = bool(packet[1] & 0x80)
    payload_type = packet[1] & 0x7F
    offset = 12 + 4 * csrc_count
    timestamp: datetime | None = None
    if has_extension:
        if len(packet) < offset + 4:
            return None
        profile = int.from_bytes(packet[offset:offset + 2], "big")
        words = int.from_bytes(packet[offset + 2:offset + 4], "big")
        extension = packet[offset + 4:offset + 4 + 4 * words]
        if profile == ONVIF_REPLAY_EXTENSION and len(extension) >= 8:
            seconds = int.from_bytes(extension[0:4], "big")
            fraction = int.from_bytes(extension[4:8], "big") / 2**32
            timestamp = NTP_EPOCH + timedelta(seconds=seconds + fraction)
        offset += 4 + 4 * words
    end = len(packet)
    if has_padding and end > offset:
        end -= packet[-1]
    if end < offset:
        return None
    return marker, payload_type, timestamp, packet[offset:end]


def _parse_sdp(sdp: str) -> _Track | None:
    track: _Track | None = None
    for line in sdp.splitlines():
        line = line.strip()
        if line.startswith("m="):
            if track and track.payload_type >= 0:
                break
            parts = line[2:].split()
            if parts and parts[0] == "video" and len(parts) >= 4:
                track = _Track(control="", codec="", payload_type=int(parts[3]))
            else:
                track = None
        elif track is not None and line.startswith("a=rtpmap:"):
            match = re.match(r"a=rtpmap:(\d+)\s+([A-Za-z0-9]+)", line)
            if match and int(match.group(1)) == track.payload_type:
                name = match.group(2).upper()
                track.codec = "h265" if name in ("H265", "HEVC") else "h264" if name == "H264" else name.lower()
        elif track is not None and line.startswith("a=control:"):
            track.control = line[len("a=control:"):].strip()
        elif track is not None and line.startswith("a=fmtp:"):
            for key in ("sprop-vps", "sprop-sps", "sprop-pps", "sprop-parameter-sets"):
                match = re.search(rf"{key}=([^;\s]+)", line)
                if match:
                    for chunk in match.group(1).split(","):
                        try:
                            track.parameter_sets.append(base64.b64decode(chunk + "=" * (-len(chunk) % 4)))
                        except ValueError:
                            continue
    return track if track and track.codec in ("h264", "h265") else None


def _clock_range(start: datetime, end: datetime) -> str:
    fmt = "%Y%m%dT%H%M%S.%fZ"
    return f"clock={start.astimezone(timezone.utc).strftime(fmt)[:-4]}Z-{end.astimezone(timezone.utc).strftime(fmt)[:-4]}Z"


class _RtspConnection:
    def __init__(self, uri: str, username: str, password: str, timeout: float) -> None:
        parts = urlsplit(uri)
        if parts.scheme.lower() != "rtsp" or not parts.hostname:
            raise ReplayError("URI de replay inválida.")
        self.uri = uri
        self.username = username
        self.password = password
        self.cseq = 0
        self.session: str | None = None
        self._auth: dict[str, str] | None = None
        self.sock = socket.create_connection((parts.hostname, parts.port or 554), timeout=timeout)
        self.sock.settimeout(timeout)
        self._buffer = bytearray()

    def request(self, method: str, url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
        for attempt in range(2):
            status, response_headers, body = self._send(method, url, headers or {})
            if status == 401 and attempt == 0 and self.username:
                self._auth = _parse_challenge(response_headers.get("www-authenticate", ""))
                continue
            return status, response_headers, body
        return status, response_headers, body

    def _send(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
        self.cseq += 1
        lines = [f"{method} {url} RTSP/1.0", f"CSeq: {self.cseq}", "User-Agent: MonitoraPet"]
        if self.session:
            lines.append(f"Session: {self.session}")
        if self._auth is not None:
            lines.append(f"Authorization: {_authorization(self._auth, method, url, self.username, self.password)}")
        lines.extend(f"{key}: {value}" for key, value in headers.items())
        self.sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("utf-8"))
        return self._read_response()

    def _read_response(self) -> tuple[int, dict[str, str], bytes]:
        while True:
            index = self._buffer.find(b"\r\n\r\n")
            if index >= 0:
                break
            self._fill()
        head, self._buffer = bytes(self._buffer[:index]), self._buffer[index + 4:]
        lines = head.decode("utf-8", "replace").split("\r\n")
        match = re.match(r"RTSP/1\.\d\s+(\d{3})", lines[0])
        if not match:
            raise ReplayError(f"Resposta RTSP inválida: {lines[0]!r}")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
        length = int(headers.get("content-length", "0") or 0)
        while len(self._buffer) < length:
            self._fill()
        body, self._buffer = bytes(self._buffer[:length]), self._buffer[length:]
        if session := headers.get("session"):
            self.session = session.split(";")[0].strip()
        return int(match.group(1)), headers, body

    def interleaved(self):
        while True:
            while len(self._buffer) < 4:
                if not self._fill():
                    return
            if self._buffer[0] != 0x24:
                index = self._buffer.find(b"\r\n\r\n")
                if index < 0:
                    if not self._fill():
                        return
                    continue
                del self._buffer[:index + 4]
                continue
            channel = self._buffer[1]
            length = int.from_bytes(self._buffer[2:4], "big")
            while len(self._buffer) < 4 + length:
                if not self._fill():
                    return
            packet = bytes(self._buffer[4:4 + length])
            del self._buffer[:4 + length]
            yield channel, packet

    def _fill(self) -> bool:
        chunk = self.sock.recv(65536)
        if not chunk:
            return False
        self._buffer += chunk
        return True

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def _parse_challenge(header: str) -> dict[str, str]:
    scheme, _, rest = header.partition(" ")
    params = {key.lower(): value.strip('"') for key, value in re.findall(r'(\w+)=("[^"]*"|[^,]*)', rest)}
    params["scheme"] = scheme.strip().lower()
    return params


def _authorization(challenge: dict[str, str], method: str, url: str, username: str, password: str) -> str:
    if challenge.get("scheme") == "basic":
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return f"Basic {token}"
    realm, nonce = challenge.get("realm", ""), challenge.get("nonce", "")
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode("utf-8")).hexdigest()
    ha2 = hashlib.md5(f"{method}:{url}".encode("utf-8")).hexdigest()
    qop = challenge.get("qop", "")
    if "auth" in qop.split(","):
        cnonce = os.urandom(8).hex()
        response = hashlib.md5(f"{ha1}:{nonce}:00000001:{cnonce}:auth:{ha2}".encode("utf-8")).hexdigest()
        return (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{url}", '
            f'response="{response}", qop=auth, nc=00000001, cnonce="{cnonce}"'
        )
    response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode("utf-8")).hexdigest()
    return f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{url}", response="{response}"'


class ReplayDownloader:
    def __init__(self, timeout: float = READ_TIMEOUT_SECONDS, connection_factory: Callable[..., _RtspConnection] = _RtspConnection) -> None:
        self.timeout = timeout
        self.connection_factory = connection_factory

    def download(
        self,
        uri: str,
        username: str,
        password: str,
        start: datetime,
        end: datetime,
        destination: Path,
        on_progress: Callable[[datetime], None] | None = None,
    ) -> ReplayResult:
        connection = self.connection_factory(uri, username, password, self.timeout)
        try:
            return self._download(connection, uri, start, end, destination, on_progress)
        finally:
            connection.close()

    def _download(
        self,
        connection: _RtspConnection,
        uri: str,
        start: datetime,
        end: datetime,
        destination: Path,
        on_progress: Callable[[datetime], None] | None,
    ) -> ReplayResult:
        status, _, body = connection.request("DESCRIBE", uri, {"Accept": "application/sdp", "Require": "onvif-replay"})
        if status != 200:
            raise ReplayError(f"A câmera recusou o replay (DESCRIBE {status}).")
        track = _parse_sdp(body.decode("utf-8", "replace"))
        if track is None:
            raise ReplayError("O replay não anunciou uma trilha de vídeo H.264 ou H.265.")
        control = _resolve_control(uri, track.control)
        status, _, _ = connection.request(
            "SETUP", control, {"Transport": "RTP/AVP/TCP;unicast;interleaved=0-1", "Require": "onvif-replay"}
        )
        if status != 200:
            raise ReplayError(f"A câmera recusou o replay (SETUP {status}).")
        status, _, _ = connection.request(
            "PLAY",
            uri,
            {"Range": _clock_range(start, end), "Rate-Control": "no", "Immediate": "yes", "Require": "onvif-replay"},
        )
        if status != 200:
            raise ReplayError(f"A câmera recusou o replay (PLAY {status}).")
        destination.parent.mkdir(parents=True, exist_ok=True)
        timestamps: list[float] = []
        first: datetime | None = None
        last: datetime | None = None
        frames = 0
        depacketizer = _Depacketizer(track.codec)
        pending_timestamp: datetime | None = None
        with destination.open("wb") as handle:
            for parameter_set in track.parameter_sets:
                handle.write(START_CODE + parameter_set)
            try:
                for channel, packet in connection.interleaved():
                    if channel != 0:
                        continue
                    parsed = parse_rtp(packet)
                    if parsed is None:
                        continue
                    marker, payload_type, timestamp, payload = parsed
                    if payload_type != track.payload_type:
                        continue
                    if timestamp is not None and pending_timestamp is None:
                        pending_timestamp = timestamp
                    for unit in depacketizer.units(payload):
                        handle.write(START_CODE + unit)
                    if marker:
                        frame_time = pending_timestamp or timestamp
                        pending_timestamp = None
                        frames += 1
                        if frame_time is not None:
                            first = first or frame_time
                            last = frame_time
                            timestamps.append(frame_time.timestamp())
                            if on_progress:
                                on_progress(frame_time)
                            if frame_time >= end:
                                break
            except (socket.timeout, TimeoutError):
                logger.info("Replay encerrado por inatividade após %d quadros", frames)
        try:
            connection.request("TEARDOWN", uri)
        except (OSError, ReplayError):
            pass
        if frames == 0:
            destination.unlink(missing_ok=True)
            raise ReplayError("A câmera não enviou nenhum quadro para o período pedido.")
        index_path = index_path_for(destination)
        index_path.write_text(json.dumps({"codec": track.codec, "timestamps": timestamps}), encoding="utf-8")
        return ReplayResult(destination, track.codec, frames, first, last)


def _resolve_control(uri: str, control: str) -> str:
    if not control or control == "*":
        return uri
    if "://" in control:
        return control
    return uri.rstrip("/") + "/" + control.lstrip("/")


def index_path_for(path: Path) -> Path:
    return path.with_name(path.name + ".index.json")
