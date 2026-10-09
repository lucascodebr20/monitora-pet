# Como contribuir

Obrigado pelo interesse no Monitora Pet! Issues, correções, testes com novas
câmeras e melhorias na documentação são bem-vindos.

> **English speakers:** issues and pull requests in English are welcome too.

## Antes de começar

- Para mudanças grandes, abra uma issue antes e descreva a ideia. Assim
  evitamos trabalho duplicado.
- Problemas de segurança **não** vão em issues públicas: veja [SECURITY.md](SECURITY.md).
- Ao participar, você concorda com o [código de conduta](CODE_OF_CONDUCT.md).

## Ambiente de desenvolvimento

Requisitos: Windows 10/11 (o armazenamento de credenciais usa DPAPI),
Python 3.13+ e Node.js 22+. O app desktop também precisa de Rust (Tauri).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r back\requirements-dev.txt

# baixa os modelos ONNX (uma vez)
Set-Location back
..\.venv\Scripts\python.exe -m app.infra.ai.model_setup
Set-Location ..

# backend em http://127.0.0.1:8000
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir back --reload

# frontend (Vite encaminha /api para o backend)
Set-Location front
npm ci
npm run dev
```

Também dá para subir tudo com `.\start.bat` ou com Docker (`docker compose up`).

Não é preciso ter uma câmera IP para desenvolver: cadastre uma câmera
"pelo cartão de memória" e importe vídeos de uma pasta.

## Testes e verificações

Rode antes de abrir o pull request (a CI roda os mesmos comandos):

```powershell
# backend
Set-Location back
..\.venv\Scripts\python.exe -m unittest discover -s tests

# frontend
Set-Location front
npm run lint
npm test
npm run build
```

Mudanças na identificação de pets devem informar o resultado de
`back/tools/evaluate_identification.py` antes e depois.

## Organização do código

- `back/app/controllers`: rotas REST e schemas.
- `back/app/services`: casos de uso.
- `back/app/domain`: regras puras, sem I/O.
- `back/app/infra`: SQLite, câmeras, IA, mídia.
- `back/app/infra/database/migrations`: migrações SQL numeradas. Nunca altere
  uma migração existente; crie a próxima.
- `front/src`: interface React; `front/src-tauri`: casca desktop.
- `desktop/`: empacotamento (PyInstaller, Tauri, MSIX).

## Commits e pull requests

- Use mensagens no formato [Conventional Commits](https://www.conventionalcommits.org/pt-br/):
  `feat(identification): ...`, `fix(camera): ...`, `docs: ...`, `chore: ...`.
- Um pull request por assunto, com testes para o comportamento novo ou corrigido.
- Descreva como testou, incluindo marca e modelo da câmera quando for relevante.

## Licença

Ao enviar uma contribuição, você concorda que ela seja licenciada sob a
[Apache License 2.0](LICENSE), a mesma do projeto.
