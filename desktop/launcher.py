from __future__ import annotations

import argparse
import os
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


LEGACY_APP_NAMES = ("MonitoraPet",)


def default_data_dir() -> Path:
    base = Path(os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share"))
    current = base / "VigiaPet"
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


def wait_until_ready(url: str, token: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.25)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VigiaPet")
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


def main() -> int:
    args = parse_args()
    root = bundle_root()


    os.environ.setdefault("VIGIAPET_DATA_DIR", str(default_data_dir()))
    os.environ.setdefault("VIGIAPET_FRONTEND_DIST", str(root / "front" / "dist"))
    token = os.environ.get("VIGIAPET_API_TOKEN") or secrets.token_urlsafe(32)
    os.environ["VIGIAPET_API_TOKEN"] = token

    print(f"VigiaPet · dados em {os.environ['VIGIAPET_DATA_DIR']}")

    from app.infra.ai.model_setup import ensure_models

    try:
        print("Verificando os modelos de inteligência artificial (download só no primeiro uso)...")
        ensure_models()
    except Exception as error:
        print(f"Aviso: não foi possível preparar os modelos de IA agora ({error}).")

    import uvicorn

    from app.main import app

    port = args.port or free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="vigiapet-server", daemon=True)
    thread.start()

    if not wait_until_ready(f"{base_url}/api/session", token):
        print("O serviço do VigiaPet não respondeu a tempo.")
        server.should_exit = True
        return 1

    print(f"VigiaPet pronto em {base_url}")
    if args.no_window:
        keep_serving(thread)
        server.should_exit = True
        thread.join(timeout=15)
        return 0

    start_url = f"{base_url}/?token={token}"
    opened_window = False
    if not args.browser:
        try:
            import webview

            webview.create_window("VigiaPet", start_url, width=1280, height=820, min_size=(960, 640))
            webview.start()
            opened_window = True
        except Exception as error:
            print(f"Janela nativa indisponível ({error}); abrindo no navegador padrão.")
    if not opened_window:
        webbrowser.open(start_url)
        print("Feche esta janela para encerrar o VigiaPet.")
        keep_serving(thread)

    server.should_exit = True
    thread.join(timeout=15)
    return 0


if __name__ == "__main__":
    sys.exit(main())
