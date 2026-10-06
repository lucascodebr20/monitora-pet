param(
    [string]$PackageIdentityName = $env:VIGIAPET_STORE_IDENTITY_NAME,
    [string]$Publisher = $env:VIGIAPET_STORE_PUBLISHER,
    [string]$PublisherDisplayName = $env:VIGIAPET_STORE_PUBLISHER_DISPLAY_NAME,
    [string]$WebView2Version = "154.0.4258.62",
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"
$Builder = Join-Path $PSScriptRoot "build_msix.ps1"
& $Builder `
    -PackageIdentityName $PackageIdentityName `
    -Publisher $Publisher `
    -PublisherDisplayName $PublisherDisplayName `
    -WebView2Version $WebView2Version `
    -SkipAppBuild:$SkipAppBuild
