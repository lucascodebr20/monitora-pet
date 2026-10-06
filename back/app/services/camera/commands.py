from dataclasses import dataclass

@dataclass(frozen=True)
class CreateCameraCommand:
    name: str
    ip: str
    username: str
    password: str
    rtsp_url: str | None
    onvif_port: int


@dataclass(frozen=True)
class CameraCredentialsCommand:
    username: str
    password: str
    rtsp_url: str | None
