"""Ponto de entrada do executável desktop do MonitoraPet.

Fluxo ao clicar no ícone:
  1. define a pasta de dados do usuário (LOCALAPPDATA/MonitoraPet) e o frontend embutido;
  2. gera uma chave de sessão aleatória, válida só para esta execução;
  3. garante os modelos de IA (download no primeiro uso);
  4. sobe o backend em uma porta livre, apenas em 127.0.0.1;
  5. abre uma janela nativa (WebView2) já autenticada; sem pywebview, abre o navegador padrão.

O mesmo binário serve de sidecar para o Tauri: basta ele passar MONITORAPET_API_TOKEN,
--port e --no-window, e abrir a própria janela em http://127.0.0.1:<porta>/?token=<chave>.
"""

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


def default_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "MonitoraPet"


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
    parser = argparse.ArgumentParser(description="MonitoraPet")
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

    # Variáveis precisam existir antes de importar o app, pois o config as lê na importação.
    os.environ.setdefault("MONITORAPET_DATA_DIR", str(default_data_dir()))
    os.environ.setdefault("MONITORAPET_FRONTEND_DIST", str(root / "front" / "dist"))
    token = os.environ.get("MONITORAPET_API_TOKEN") or secrets.token_urlsafe(32)
    os.environ["MONITORAPET_API_TOKEN"] = token

    print(f"MonitoraPet · dados em {os.environ['MONITORAPET_DATA_DIR']}")

    from app.infra.ai.model_setup import ensure_models

    try:
        print("Verificando os modelos de inteligência artificial (download só no primeiro uso)...")
        ensure_models()
    except Exception as error:  # sem internet, o app abre e avisa que o modelo falta
        print(f"Aviso: não foi possível preparar os modelos de IA agora ({error}).")

    import uvicorn

    from app.main import app

    port = args.port or free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="monitorapet-server", daemon=True)
    thread.start()

    if not wait_until_ready(f"{base_url}/api/session", token):
        print("O serviço do MonitoraPet não respondeu a tempo.")
        server.should_exit = True
        return 1

    print(f"MonitoraPet pronto em {base_url}")
    if args.no_window:
        keep_serving(thread)
        server.should_exit = True
        return 0

    start_url = f"{base_url}/?token={token}"
    opened_window = False
    if not args.browser:
        try:
            import webview

            webview.create_window("MonitoraPet", start_url, width=1280, height=820, min_size=(960, 640))
            opened_window = True
            webview.start()
        except Exception as error:
            if opened_window:
                raise
            print(f"Janela nativa indisponível ({error}); abrindo no navegador padrão.")
    if not opened_window:
        webbrowser.open(start_url)
        print("Feche esta janela para encerrar o MonitoraPet.")
        keep_serving(thread)

    server.should_exit = True
    thread.join(timeout=15)
    return 0


if __name__ == "__main__":
    sys.exit(main())
