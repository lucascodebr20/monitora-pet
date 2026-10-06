@echo off
setlocal
cd /d "%~dp0"

set "VIGIAPET_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%VIGIAPET_PYTHON%" (
    echo Preparando o Monitora Pet pela primeira vez...
    py -3 -m venv .venv || exit /b 1
    "%VIGIAPET_PYTHON%" -m pip install --upgrade pip || exit /b 1
    "%VIGIAPET_PYTHON%" -m pip install -r back\requirements.txt || exit /b 1
)

if not exist "front\node_modules" (
    echo Preparando a interface pela primeira vez...
    pushd front
    call npm.cmd install || exit /b 1
    popd
)

echo Verificando o modelo de inteligencia artificial...
pushd back
"%VIGIAPET_PYTHON%" -m app.infra.ai.model_setup || exit /b 1
popd

echo Construindo a interface...
pushd front
call npm.cmd run build || exit /b 1
popd
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"`) do set "VIGIAPET_API_TOKEN=%%t"
if not defined VIGIAPET_API_TOKEN (
    echo Nao foi possivel gerar a chave de sessao.
    exit /b 1
)

echo Monitora Pet disponivel em http://127.0.0.1:8000
start "" "http://127.0.0.1:8000/?token=%VIGIAPET_API_TOKEN%"
"%VIGIAPET_PYTHON%" -m uvicorn app.main:app --app-dir back --host 127.0.0.1 --port 8000

endlocal
