@echo off
setlocal
cd /d "%~dp0"

set "MONITORAPET_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%MONITORAPET_PYTHON%" (
    echo Preparando o MonitoraPet pela primeira vez...
    py -3 -m venv .venv || exit /b 1
    "%MONITORAPET_PYTHON%" -m pip install --upgrade pip || exit /b 1
    "%MONITORAPET_PYTHON%" -m pip install -r back\requirements.txt || exit /b 1
)

if not exist "front\node_modules" (
    echo Preparando a interface pela primeira vez...
    pushd front
    call npm.cmd install || exit /b 1
    popd
)

echo Verificando o modelo de inteligencia artificial...
pushd back
"%MONITORAPET_PYTHON%" -m app.infra.ai.model_setup || exit /b 1
popd

echo Construindo a interface...
pushd front
call npm.cmd run build || exit /b 1
popd

rem Chave de sessao unica por execucao: a API so responde a quem a apresentar.
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"`) do set "MONITORAPET_API_TOKEN=%%t"
if not defined MONITORAPET_API_TOKEN (
    echo Nao foi possivel gerar a chave de sessao.
    exit /b 1
)

echo MonitoraPet disponivel em http://127.0.0.1:8000
start "" "http://127.0.0.1:8000/?token=%MONITORAPET_API_TOKEN%"
"%MONITORAPET_PYTHON%" -m uvicorn app.main:app --app-dir back --host 127.0.0.1 --port 8000

endlocal
