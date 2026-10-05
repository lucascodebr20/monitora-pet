from __future__ import annotations

from app.infra.camera.onvif import stream_urls
from app.infra.camera.stream import authenticate_urls, candidate_urls


def resolve_connection_urls(ip: str, onvif_port: int, rtsp_url: str | None, username: str, password: str) -> list[str]:
    if rtsp_url:
        return candidate_urls(ip, username, password, rtsp_url)
    announced = stream_urls(ip, onvif_port, username, password)
    urls = authenticate_urls(announced, username, password)
    urls.extend(candidate_urls(ip, username, password, None))
    return list(dict.fromkeys(urls))
