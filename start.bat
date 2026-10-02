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

echo Construindo a interface...
pushd front
call npm.cmd run build || exit /b 1
popd

echo MonitoraPet disponivel em http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
"%MONITORAPET_PYTHON%" -m uvicorn app.main:app --app-dir back --host 127.0.0.1 --port 8000

endlocal
