import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT / "back"))

datas = [
    (str(ROOT / "front" / "dist"), "front/dist"),
    (str(ROOT / "back" / "app" / "infra" / "database" / "migrations"), "app/infra/database/migrations"),
    (str(ROOT / "back" / "app-data" / "models" / "yolox_tiny.onnx"), "bundled-models"),
    (str(ROOT / "back" / "app-data" / "models" / "mobilenetv2_embedding.onnx"), "bundled-models"),
]
hiddenimports = collect_submodules("app") + [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
]

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT / "back")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "unittest", "pytest", "webview", "pythonnet", "clr"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="monitorapet-backend",
    icon=str(ROOT / "desktop" / "monitorapet.ico"),
    console=True,
    upx=False,
    bootloader_ignore_signals=False,
    strip=False,
)
