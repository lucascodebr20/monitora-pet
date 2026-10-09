# Política de segurança

O Monitora Pet lida com credenciais de câmeras e vídeos da casa das pessoas.
Levamos relatos de segurança a sério.

## Como reportar

**Não abra uma issue pública.** Use o reporte privado do GitHub:
aba **Security → Report a vulnerability** deste repositório.

Inclua, se possível:

- versão do app (Configurações → Sobre, ou `front/package.json`);
- como reproduzir e o impacto esperado;
- se o problema exige acesso à rede local ou funciona remotamente.

Você recebe uma resposta inicial em até 7 dias. Depois da correção,
publicamos uma nova versão e damos crédito a quem reportou, se quiser.

## Versões suportadas

Apenas a versão mais recente publicada na Microsoft Store e a branch `main`
recebem correções de segurança.

## Escopo

Pontos especialmente relevantes:

- vazamento de credenciais de câmeras (armazenadas com DPAPI em `credentials.bin`);
- acesso à API sem token ou a partir de outro host (proteção contra DNS rebinding);
- leitura de vídeos, fotos ou banco de dados por outro usuário ou processo;
- execução de código a partir de arquivos de vídeo, pastas vigiadas ou respostas de câmeras (ONVIF, SSDP, WS-Discovery).

Fora do escopo: vulnerabilidades no firmware das câmeras e ataques que já
exigem controle total da conta Windows do usuário.
