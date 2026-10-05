@echo off
setlocal
cd /d "%~dp0.."

set "VIGIAPET_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%VIGIAPET_PYTHON%" (
    echo Criando ambiente Python...
    py -3 -m venv .venv || exit /b 1
    "%VIGIAPET_PYTHON%" -m pip install --upgrade pip || exit /b 1
)

echo Instalando dependencias do backend e do empacotador...
"%VIGIAPET_PYTHON%" -m pip install -q -r back\requirements.txt pyinstaller || exit /b 1
"%VIGIAPET_PYTHON%" -m pip install -q pywebview || echo Aviso: pywebview indisponivel, o executavel abrira no navegador.

if not exist "front\node_modules" (
    echo Instalando dependencias da interface...
    pushd front
    call npm.cmd ci || exit /b 1
    popd
)

echo Construindo a interface...
pushd front
call npm.cmd run build || exit /b 1
popd

echo Gerando o executavel...
"%VIGIAPET_PYTHON%" -m PyInstaller --noconfirm --clean --distpath desktop\dist --workpath desktop\build desktop\vigiapet.spec || exit /b 1

echo.
echo Pronto: desktop\dist\VigiaPet.exe
endlocal
