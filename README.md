# MonitoraPet

Aplicação local e open source para acompanhar visitas de gatos às áreas de
comida, água e caixa de areia usando câmeras IP existentes.

O vídeo, o histórico e os dados de configuração permanecem no computador do
usuário. O projeto não envia imagens ou credenciais para serviços externos.

## Estrutura

```text
front/  React, TypeScript e Vite
back/   FastAPI, SQLite, ONVIF e RTSP
```

O backend usa uma arquitetura em camadas: controllers REST, services de casos
de uso, domínio independente, repositories e infraestrutura SQLite com
migrações versionadas. Ele oferece cadastro e operação independente de câmeras,
zonas normalizadas, histórico de eventos, fila de revisão humana, avisos locais
e estado de saúde. A interface é responsiva para desktop e dispositivos na
rede local.

## Executar no Windows

Confirme que o computador e as câmeras estão na mesma rede. Depois execute:

```powershell
.\start.bat
```

Na primeira execução, o script prepara as dependências. Em seguida, o
MonitoraPet fica disponível em `http://127.0.0.1:8000`.

## Desenvolvimento

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir back --reload
```

Frontend:

```powershell
Set-Location front
npm.cmd run dev
```

O Vite encaminha as chamadas `/api` para o backend local.

## Testes

```powershell
Set-Location back
..\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Privacidade

Senhas de câmera são usadas somente para abrir a conexão e não são persistidas
no SQLite nem retornadas pela API. Arquivos locais de dados, ambientes e
documentação de trabalho são ignorados pelo Git.
