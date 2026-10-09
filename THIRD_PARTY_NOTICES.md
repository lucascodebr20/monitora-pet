# Componentes de terceiros

O Monitora Pet usa os componentes abaixo. Todos têm licenças permissivas
compatíveis com a Apache-2.0. As versões exatas estão em
`back/requirements.txt`, `front/package-lock.json` e
`front/src-tauri/Cargo.lock`.

## Modelos de IA

Baixados na primeira execução (e embutidos no pacote da Microsoft Store), com
SHA-256 verificado em `back/app/infra/ai/model_setup.py`. Não ficam no Git.

| Modelo | Uso | Licença | Origem |
| --- | --- | --- | --- |
| YOLOX-Tiny (ONNX) | Detecção de gatos e cães | Apache-2.0 | [Megvii-BaseDetection/YOLOX](https://github.com/Megvii-BaseDetection/YOLOX) |
| MobileNetV2 2022apr (ONNX) | Embeddings para identificar cada pet | Apache-2.0 | [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo) |

## Backend (Python)

| Componente | Licença |
| --- | --- |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause |
| [OpenCV (opencv-python-headless)](https://github.com/opencv/opencv-python) | Apache-2.0 (o wheel inclui FFmpeg sob LGPL-2.1) |

## Frontend e app desktop

| Componente | Licença |
| --- | --- |
| [React](https://github.com/facebook/react) | MIT |
| [Vite](https://github.com/vitejs/vite) | MIT |
| [Tauri](https://github.com/tauri-apps/tauri) e plugins | MIT ou Apache-2.0 |
| [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (embutido só no MSIX) | Licença da Microsoft para redistribuição |

As demais dependências transitivas mantêm suas próprias licenças, disponíveis
nos respectivos pacotes.
