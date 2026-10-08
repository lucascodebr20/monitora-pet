from __future__ import annotations

import argparse
import os
import secrets
import shutil
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


LEGACY_APP_NAMES = ("VigiaPet",)


def default_data_dir() -> Path:
    base = Path(os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share"))
    current = base / "MonitoraPet"
    if current.exists():
        return current

    for legacy_name in LEGACY_APP_NAMES:
        legacy = base / legacy_name
        if legacy.is_dir():
            try:
                legacy.rename(current)
                print(f"Dados migrados de {legacy} para {current}")
                return current
            except OSError as error:
                print(f"Aviso: não foi possível mover {legacy} para {current} ({error}); usando a pasta antiga.")
                return legacy
    return current


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def wait_until_ready(url: str, token: str, server_thread: threading.Thread, timeout: float = 120.0) -> bool:
    deadline = time.monotonic() + timeout
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    while time.monotonic() < deadline and server_thread.is_alive():
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.25)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitora Pet")
    parser.add_argument("--port", type=int, default=0, help="porta local (0 = escolher uma livre)")
    parser.add_argument("--no-window", action="store_true", help="não abrir janela nem navegador (modo sidecar)")
    parser.add_argument("--browser", action="store_true", help="abrir no navegador padrão em vez da janela nativa")
    return parser.parse_args()


def keep_serving(thread: threading.Thread) -> None:
    try:
        while thread.is_alive():
            thread.join(timeout=1)
    except KeyboardInterrupt:
        pass


def prepare_models(root: Path) -> None:
    from app.core.config import MODEL_PATH, PET_EMBEDDING_MODEL_PATH, ensure_data_directories
    from app.infra.ai.model_setup import (
        MODEL_SHA256,
        PET_EMBEDDING_MODEL_SHA256,
        ensure_models,
        file_hash,
    )

    if not getattr(sys, "frozen", False):
        ensure_models()
        return

    ensure_data_directories()
    bundled_dir = root / "bundled-models"
    models = (
        (bundled_dir / "yolox_tiny.onnx", MODEL_PATH, MODEL_SHA256),
        (bundled_dir / "mobilenetv2_embedding.onnx", PET_EMBEDDING_MODEL_PATH, PET_EMBEDDING_MODEL_SHA256),
    )
    for source, target, expected_hash in models:
        if target.is_file() and file_hash(target) == expected_hash:
            continue
        if not source.is_file() or file_hash(source) != expected_hash:
            raise RuntimeError(f"Modelo de IA ausente ou inválido no pacote: {source.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".bundled")
        shutil.copyfile(source, temporary)
        if file_hash(temporary) != expected_hash:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"Falha ao validar o modelo empacotado: {source.name}")
        temporary.replace(target)


def main() -> int:
    args = parse_args()
    root = bundle_root()

    os.environ.setdefault("MONITORAPET_DATA_DIR", str(default_data_dir()))
    os.environ.setdefault("MONITORAPET_FRONTEND_DIST", str(root / "front" / "dist"))
    token = os.environ.get("MONITORAPET_API_TOKEN") or secrets.token_urlsafe(32)
    os.environ["MONITORAPET_API_TOKEN"] = token

    print(f"Monitora Pet · dados em {os.environ['MONITORAPET_DATA_DIR']}")

    try:
        print("Preparando os modelos de inteligência artificial...", flush=True)
        prepare_models(root)
    except Exception as error:
        print(f"Não foi possível preparar os modelos de IA ({error}).", flush=True)
        traceback.print_exc()
        return 1

    import uvicorn

    from app.main import app

    port = args.port or free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="monitorapet-server", daemon=True)
    thread.start()

    if not wait_until_ready(f"{base_url}/api/session", token, thread):
        if thread.is_alive():
            print("O serviço do Monitora Pet não respondeu a tempo.", flush=True)
        else:
            print("O serviço do Monitora Pet parou durante a inicialização.", flush=True)
        server.should_exit = True
        return 1

    print(f"Monitora Pet pronto em {base_url}", flush=True)
    start_url = f"{base_url}/?token={token}"
    if args.no_window:
        print(f"MONITORAPET_READY={start_url}", flush=True)
        keep_serving(thread)
        server.should_exit = True
        thread.join(timeout=15)
        return 0

    opened_window = False
    if not args.browser:
        try:
            import webview

            webview.create_window("Monitora Pet", start_url, width=1280, height=820, min_size=(960, 640))
            webview.start()
            opened_window = True
        except Exception as error:
            print(f"Janela nativa indisponível ({error}); abrindo no navegador padrão.")
    if not opened_window:
        webbrowser.open(start_url)
        print("Feche esta janela para encerrar o Monitora Pet.")
        keep_serving(thread)

    server.should_exit = True
    thread.join(timeout=15)
    return 0


def run() -> int:
    configure_console()
    try:
        return main()
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        return 1


if __name__ == "__main__":
    sys.exit(run())
