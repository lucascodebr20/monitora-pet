param(
    [string]$TargetTriple = "x86_64-pc-windows-msvc"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FrontDir = Join-Path $ProjectRoot "front"
$BackDir = Join-Path $ProjectRoot "back"
$TauriBinDir = Join-Path $FrontDir "src-tauri\binaries"

if (-not (Test-Path -LiteralPath $Python)) {
    py -3 -m venv (Join-Path $ProjectRoot ".venv")
}

& $Python -m pip install -q -r (Join-Path $BackDir "requirements.txt") pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências de build do backend." }

Push-Location $BackDir
try {
    & $Python -m app.infra.ai.model_setup
    if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar os modelos de IA para o pacote." }
}
finally {
    Pop-Location
}

Push-Location $FrontDir
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o frontend." }
}
finally {
    Pop-Location
}

& $Python -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $ProjectRoot "desktop\dist-tauri") `
    --workpath (Join-Path $ProjectRoot "desktop\build-tauri") `
    (Join-Path $ProjectRoot "desktop\monitorapet-backend.spec")
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o sidecar do backend." }

New-Item -ItemType Directory -Force -Path $TauriBinDir | Out-Null
$Source = Join-Path $ProjectRoot "desktop\dist-tauri\monitorapet-backend.exe"
$Destination = Join-Path $TauriBinDir "monitorapet-backend-$TargetTriple.exe"
Copy-Item -LiteralPath $Source -Destination $Destination -Force

if ($env:MONITORAPET_CERTIFICATE_THUMBPRINT) {
    $SignTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $SignTool) { throw "signtool.exe não encontrado no Windows SDK." }
    $TimestampUrl = if ($env:MONITORAPET_TIMESTAMP_URL) { $env:MONITORAPET_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }
    & $SignTool sign /sha1 $env:MONITORAPET_CERTIFICATE_THUMBPRINT /fd SHA256 /tr $TimestampUrl /td SHA256 $Destination
    if ($LASTEXITCODE -ne 0) { throw "Falha ao assinar o sidecar do backend." }
}
else {
    Write-Host "Sidecar gerado sem assinatura individual (válido para envio dentro do MSIX à Microsoft Store)."
}

Write-Host "Sidecar offline preparado em $Destination"
