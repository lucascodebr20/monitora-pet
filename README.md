# Monitora Pet

Aplicação local e open source para acompanhar visitas de gatos e cães às áreas
de comida, água e banheiro (caixa de areia ou tapete) usando câmeras IP existentes.

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
zonas normalizadas, histórico de eventos, fila de revisão humana, análise de
gravações do cartão de memória e estado de saúde. A interface é responsiva para desktop e dispositivos na
rede local.

## Zonas e inteligência artificial

O editor permite desenhar polígonos diretamente sobre o vídeo, mover seus
vértices e configurar permanência, tolerância e cooldown. A detecção local usa
YOLOX-Tiny em formato ONNX pelo OpenCV. Caixas e estados das zonas aparecem em
tempo real; uma permanência confirmada gera evento e snapshot para revisão.

O `start.bat` baixa o modelo oficial na primeira execução e valida seu SHA-256.
O arquivo permanece em `back/app-data/models` e não é enviado ao Git. YOLOX é
distribuído sob Apache-2.0 pelo projeto Megvii-BaseDetection.

## Gravações do cartão de memória

O computador não precisa ficar ligado o dia inteiro. A câmera grava no cartão
de memória e o Monitora Pet analisa as gravações depois, em segundo plano, com
as mesmas zonas, eventos, fotos e vídeos do modo ao vivo.

Há três caminhos para as gravações chegarem ao aplicativo:

- **Download direto da câmera**: câmeras com ONVIF Profile G (busca e replay
  de gravações) são detectadas no cadastro. O botão "Baixar da câmera" traz só
  os períodos que o modo ao vivo não cobriu, corrigindo a hora pelo relógio da
  câmera. O download usa RTSP de replay e grava arquivos H.264/H.265 em
  `<dados>/recordings`.
- **Pasta vigiada**: copie os vídeos do cartão para uma pasta e cadastre-a em
  "Gravações". A pasta é varrida ao abrir o aplicativo e a cada importação. A
  hora de início vem do nome do arquivo ou da data de modificação e pode ser
  ajustada manualmente.
- **Câmera manual**: uma câmera cadastrada "pelo cartão de memória" não tem
  endereço de rede e só recebe gravações por pasta. Pode ser convertida em
  câmera de rede depois sem perder zonas nem histórico.

Cada gravação é identificada por uma impressão digital do arquivo, então
importar a mesma pasta duas vezes não duplica eventos. "Reprocessar" apaga os
eventos daquela gravação e a devolve à fila. A análise continua em segundo
plano mesmo com a janela fechada: no desktop o aplicativo vai para a bandeja e
volta quando termina. Gravações baixadas, fotos e vídeos de eventos são
apagados após o período de retenção configurado (7 dias por padrão); os
registros das visitas permanecem.

As credenciais das câmeras ficam cifradas com DPAPI em `<dados>/credentials.bin`
para reconectar no início e sincronizar sem pedir a senha novamente.

## Executar no Windows

Confirme que o computador e as câmeras estão na mesma rede. Depois execute:

```powershell
.\start.bat
```

Na primeira execução, o script prepara as dependências. Em seguida, o
Monitora Pet fica disponível em `http://127.0.0.1:8000`.

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
..\.venv\Scripts\python.exe -m pip install -r back\requirements-dev.txt
Set-Location back
..\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Acesso à API

O backend só aceita requisições com cabeçalho `Host` local (`127.0.0.1`, `localhost`),
o que bloqueia ataques de DNS rebinding a partir de páginas maliciosas. Outros hosts
podem ser liberados com `VIGIAPET_ALLOWED_HOSTS=meu-pc.local,192.168.1.10`.

Quando `VIGIAPET_API_TOKEN` está definido, toda rota `/api/*` exige o token, enviado
por `Authorization: Bearer <token>` ou pelo cookie HttpOnly criado em `POST /api/session`.
O iniciador do app (`start.bat` ou o Tauri) gera um token novo a cada execução e o entrega
ao frontend por `?token=` na URL inicial ou por `window.__VIGIAPET_TOKEN__`.
Sem a variável, a API responde sem token, mas continua restrita ao host local.

## Empacotamento para Microsoft Store

O pacote MSIX inclui o frontend, o backend Python, as dependências nativas, os dois
modelos ONNX e uma versão fixa do WebView2. O computador do usuário não precisa baixar
componentes na instalação nem na primeira execução.

Crie o produto no Partner Center como **MSIX ou PWA**. Na página **Identidade do
produto**, copie exatamente o nome da identidade do pacote, o editor e o nome de
exibição do editor. Depois execute:

```powershell
.\desktop\build_store.ps1 `
  -PackageIdentityName "IDENTIDADE_EXATA_DA_STORE" `
  -Publisher "CN=EDITOR_EXATO_DA_STORE" `
  -PublisherDisplayName "NOME_PUBLICO_DO_EDITOR"
```

O artefato é criado em `desktop\dist-store\MonitoraPet_<versão>_x64.msix`. Ele não precisa
de certificado próprio para envio pelo Partner Center: a Microsoft Store assina o MSIX
depois da certificação. Para instalar o pacote diretamente fora da Store, seria necessária
uma assinatura própria.

Para preparar uma atualização, sincronize a versão e gere outro MSIX com os mesmos dados
de identidade:

```powershell
.\desktop\set_version.ps1 -Version 0.3.0
.\desktop\build_store.ps1 `
  -PackageIdentityName "IDENTIDADE_EXATA_DA_STORE" `
  -Publisher "CN=EDITOR_EXATO_DA_STORE" `
  -PublisherDisplayName "NOME_PUBLICO_DO_EDITOR"
```

A Store distribui a nova versão automaticamente aos clientes depois que o novo envio é
certificado e publicado.

## Diagnóstico

O backend grava um log rotativo em `<pasta de dados>/logs/vigiapet.log` (no executável,
`%LOCALAPPDATA%\MonitoraPet\logs`). Falhas de modelo, de inferência e de conexão com câmeras
aparecem ali.

## Privacidade

Senhas de câmera são usadas somente para abrir a conexão e não são persistidas
no SQLite nem retornadas pela API. Arquivos locais de dados, ambientes e
documentação de trabalho são ignorados pelo Git.
