param(
    [string]$PackageIdentityName = $(if ($env:MONITORAPET_STORE_IDENTITY_NAME) { $env:MONITORAPET_STORE_IDENTITY_NAME } else { $env:VIGIAPET_STORE_IDENTITY_NAME }),
    [string]$Publisher = $(if ($env:MONITORAPET_STORE_PUBLISHER) { $env:MONITORAPET_STORE_PUBLISHER } else { $env:VIGIAPET_STORE_PUBLISHER }),
    [string]$PublisherDisplayName = $(if ($env:MONITORAPET_STORE_PUBLISHER_DISPLAY_NAME) { $env:MONITORAPET_STORE_PUBLISHER_DISPLAY_NAME } else { $env:VIGIAPET_STORE_PUBLISHER_DISPLAY_NAME }),
    [string]$WebView2Version = "154.0.4258.62",
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontDir = Join-Path $ProjectRoot "front"
$TauriDir = Join-Path $FrontDir "src-tauri"
$ReleaseDir = Join-Path $TauriDir "target\release"
$MsixDir = Join-Path $PSScriptRoot "msix"
$StageDir = Join-Path $MsixDir "staging"
$OutputDir = Join-Path $PSScriptRoot "dist-store"
$ToolsDir = Join-Path $ProjectRoot ".tools\windows-sdk"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$CargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
$RuntimeSourceDir = Join-Path $TauriDir "WebView2Runtime"

if (Test-Path -LiteralPath (Join-Path $CargoBin "cargo.exe")) {
    $env:Path = "$CargoBin;$env:Path"
}

if (-not $PackageIdentityName -or -not $Publisher -or -not $PublisherDisplayName) {
    throw @"
Faltam os dados de identidade da Microsoft Store.
No Partner Center, abra o produto MSIX e acesse Gerenciamento do produto > Identidade do produto.
Execute novamente informando:
  -PackageIdentityName '<Nome da identidade do pacote>'
  -Publisher '<Editor do pacote: CN=...>'
  -PublisherDisplayName '<Nome de exibição do editor>'
"@
}

$TauriConfig = Get-Content -LiteralPath (Join-Path $TauriDir "tauri.conf.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$Version = [string]$TauriConfig.version
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Versão inválida em tauri.conf.json: $Version"
}
$PackageVersion = "$Version.0"

if (-not $SkipAppBuild) {
    $RuntimeExecutable = Join-Path $RuntimeSourceDir "msedgewebview2.exe"
    if (-not (Test-Path -LiteralPath $RuntimeExecutable)) {
        $RuntimeExtractDir = Join-Path $TauriDir "WebView2Runtime.extracting"
        $RuntimeCab = Join-Path $ToolsDir "Microsoft.WebView2.FixedVersionRuntime.$WebView2Version.x64.cab"
        New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

        if (-not (Test-Path -LiteralPath $RuntimeCab)) {
            Write-Host "Consultando o catálogo oficial do WebView2..."
            $Catalog = Invoke-RestMethod -Uri "https://developer.microsoft.com/microsoft-edge/api/webview2"
            $Release = $Catalog | Where-Object { $_.version -eq $WebView2Version } | Select-Object -First 1
            $Build = $Release.builds | Where-Object { $_.architecture -eq "x64" } | Select-Object -First 1
            if (-not $Build.url) {
                throw "WebView2 Fixed Runtime $WebView2Version x64 não está disponível no catálogo oficial."
            }
            Write-Host "Baixando o WebView2 Fixed Runtime $WebView2Version x64..."
            Invoke-WebRequest -UseBasicParsing -Uri $Build.url -OutFile $RuntimeCab
        }

        foreach ($Directory in @($RuntimeSourceDir, $RuntimeExtractDir)) {
            if (Test-Path -LiteralPath $Directory) {
                Remove-Item -LiteralPath $Directory -Recurse -Force
            }
        }
        New-Item -ItemType Directory -Force -Path $RuntimeExtractDir | Out-Null
        & expand.exe $RuntimeCab -F:* $RuntimeExtractDir | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Falha ao extrair o WebView2 Fixed Runtime." }

        $ExtractedExecutable = Get-ChildItem -Path $RuntimeExtractDir -Filter "msedgewebview2.exe" -Recurse |
            Select-Object -First 1
        if (-not $ExtractedExecutable) { throw "O pacote do WebView2 não contém msedgewebview2.exe." }
        Copy-Item -LiteralPath $ExtractedExecutable.Directory.FullName -Destination $RuntimeSourceDir -Recurse
        Remove-Item -LiteralPath $RuntimeExtractDir -Recurse -Force
    }

    $TauriOverride = Join-Path ([System.IO.Path]::GetTempPath()) ("monitorapet-msix-{0}.json" -f [guid]::NewGuid().ToString("N"))
    $OverrideJson = @{
        bundle = @{
            windows = @{
                webviewInstallMode = @{
                    type = "fixedRuntime"
                    path = "./WebView2Runtime"
                    silent = $null
                }
            }
        }
    } | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($TauriOverride, $OverrideJson, $Utf8NoBom)

    Push-Location $FrontDir
    try {
        & npm.cmd run tauri -- build --no-bundle --config $TauriOverride
        if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o aplicativo Tauri." }
    }
    finally {
        Pop-Location
        if (Test-Path -LiteralPath $TauriOverride) {
            Remove-Item -LiteralPath $TauriOverride -Force
        }
    }
}

$DesktopExecutable = Join-Path $ReleaseDir "monitorapet-desktop.exe"
$BackendExecutable = Join-Path $ReleaseDir "monitorapet-backend.exe"
foreach ($RequiredFile in @($DesktopExecutable, $BackendExecutable)) {
    if (-not (Test-Path -LiteralPath $RequiredFile)) {
        throw "Arquivo necessário não encontrado: $RequiredFile"
    }
}
$RuntimeBuildDir = Join-Path $ReleaseDir "WebView2Runtime"
if (-not (Test-Path -LiteralPath (Join-Path $RuntimeBuildDir "msedgewebview2.exe"))) {
    throw "WebView2 Fixed Runtime não encontrado no build. Execute sem -SkipAppBuild."
}

$MakeAppx = Get-ChildItem -Path "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\makeappx.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $MakeAppx) {
    $SdkVersion = "10.0.28000.2270"
    $SdkRoot = Join-Path $ToolsDir $SdkVersion
    $SdkArchive = Join-Path $ToolsDir "Microsoft.Windows.SDK.BuildTools.$SdkVersion.zip"
    if (-not (Test-Path -LiteralPath $SdkRoot)) {
        New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null
        $SdkUrl = "https://api.nuget.org/v3-flatcontainer/microsoft.windows.sdk.buildtools/$SdkVersion/microsoft.windows.sdk.buildtools.$SdkVersion.nupkg"
        Write-Host "Baixando as ferramentas oficiais do Windows SDK..."
        Invoke-WebRequest -UseBasicParsing -Uri $SdkUrl -OutFile $SdkArchive
        Expand-Archive -LiteralPath $SdkArchive -DestinationPath $SdkRoot -Force
        Remove-Item -LiteralPath $SdkArchive -Force
    }
    $MakeAppx = Get-ChildItem -Path $SdkRoot -Filter "makeappx.exe" -Recurse |
        Where-Object { $_.FullName -match '[\\/]x64[\\/]' } |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $MakeAppx) { throw "makeappx.exe não foi encontrado no Windows SDK." }

if (Test-Path -LiteralPath $StageDir) {
    $ResolvedStage = (Resolve-Path -LiteralPath $StageDir).Path
    if (-not $ResolvedStage.StartsWith($MsixDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Diretório temporário fora da área esperada: $ResolvedStage"
    }
    Remove-Item -LiteralPath $ResolvedStage -Recurse -Force
}

$AssetsDir = Join-Path $StageDir "Assets"
New-Item -ItemType Directory -Force -Path $AssetsDir, $OutputDir | Out-Null
Copy-Item -LiteralPath $DesktopExecutable -Destination (Join-Path $StageDir "MonitoraPet.exe")
Copy-Item -LiteralPath $BackendExecutable -Destination (Join-Path $StageDir "monitorapet-backend.exe")
Copy-Item -LiteralPath $RuntimeBuildDir -Destination (Join-Path $StageDir "WebView2Runtime") -Recurse

$IconDir = Join-Path $TauriDir "icons"
foreach ($Asset in @("StoreLogo.png", "Square44x44Logo.png", "Square150x150Logo.png")) {
    Copy-Item -LiteralPath (Join-Path $IconDir $Asset) -Destination (Join-Path $AssetsDir $Asset)
}

function Escape-XmlValue([string]$Value) {
    return [System.Security.SecurityElement]::Escape($Value)
}

$Manifest = Get-Content -LiteralPath (Join-Path $MsixDir "AppxManifest.xml.template") -Raw -Encoding UTF8
$Manifest = $Manifest.Replace("__PACKAGE_IDENTITY_NAME__", (Escape-XmlValue $PackageIdentityName))
$Manifest = $Manifest.Replace("__PUBLISHER__", (Escape-XmlValue $Publisher))
$Manifest = $Manifest.Replace("__PUBLISHER_DISPLAY_NAME__", (Escape-XmlValue $PublisherDisplayName))
$Manifest = $Manifest.Replace("__VERSION__", $PackageVersion)
[System.IO.File]::WriteAllText((Join-Path $StageDir "AppxManifest.xml"), $Manifest, $Utf8NoBom)

$OutputPath = Join-Path $OutputDir "MonitoraPet_${Version}_x64.msix"
if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

& $MakeAppx pack /d $StageDir /p $OutputPath /o
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o pacote MSIX." }

$ValidationDir = Join-Path $OutputDir "validate-$Version"
if (Test-Path -LiteralPath $ValidationDir) {
    Remove-Item -LiteralPath $ValidationDir -Recurse -Force
}
& $MakeAppx unpack /p $OutputPath /d $ValidationDir /o | Out-Null
if ($LASTEXITCODE -ne 0) { throw "O pacote MSIX foi gerado, mas falhou na validação estrutural." }
Remove-Item -LiteralPath $ValidationDir -Recurse -Force

$Hash = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash
if (Test-Path -LiteralPath $StageDir) {
    Remove-Item -LiteralPath $StageDir -Recurse -Force
}
Write-Host ""
Write-Host "MSIX pronto para envio ao Partner Center:"
Write-Host $OutputPath
Write-Host "SHA-256: $Hash"
Write-Host "A Microsoft Store assinará o pacote após a certificação."
