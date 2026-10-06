param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Update-TextFile {
    param(
        [string]$Path,
        [string]$Pattern,
        [string]$Replacement
    )
    $Content = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if (-not [regex]::IsMatch($Content, $Pattern)) {
        throw "Não foi possível localizar a versão em $Path"
    }
    $Updated = $Content -replace $Pattern, $Replacement
    [System.IO.File]::WriteAllText($Path, $Updated, $Utf8NoBom)
}

Update-TextFile `
    -Path (Join-Path $ProjectRoot "back\app\core\config.py") `
    -Pattern 'APP_VERSION = "\d+\.\d+\.\d+"' `
    -Replacement "APP_VERSION = `"$Version`""

Update-TextFile `
    -Path (Join-Path $ProjectRoot "front\src-tauri\Cargo.toml") `
    -Pattern '(?m)^version = "\d+\.\d+\.\d+"' `
    -Replacement "version = `"$Version`""

Update-TextFile `
    -Path (Join-Path $ProjectRoot "front\src-tauri\tauri.conf.json") `
    -Pattern '"version": "\d+\.\d+\.\d+"' `
    -Replacement "`"version`": `"$Version`""

$PackagePath = Join-Path $ProjectRoot "front\package.json"
$Package = Get-Content -LiteralPath $PackagePath -Raw -Encoding UTF8 | ConvertFrom-Json
$Package.version = $Version
$PackageJson = $Package | ConvertTo-Json -Depth 100
[System.IO.File]::WriteAllText($PackagePath, $PackageJson + [Environment]::NewLine, $Utf8NoBom)

Push-Location (Join-Path $ProjectRoot "front")
try {
    & npm.cmd install --package-lock-only --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar o package-lock.json." }
}
finally {
    Pop-Location
}

Write-Host "Versão do Monitora Pet atualizada para $Version."
Write-Host "Execute .\desktop\build_store.ps1 para gerar o novo MSIX."
