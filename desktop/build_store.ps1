param(
    [string]$PackageIdentityName = $(if ($env:MONITORAPET_STORE_IDENTITY_NAME) { $env:MONITORAPET_STORE_IDENTITY_NAME } else { $env:VIGIAPET_STORE_IDENTITY_NAME }),
    [string]$Publisher = $(if ($env:MONITORAPET_STORE_PUBLISHER) { $env:MONITORAPET_STORE_PUBLISHER } else { $env:VIGIAPET_STORE_PUBLISHER }),
    [string]$PublisherDisplayName = $(if ($env:MONITORAPET_STORE_PUBLISHER_DISPLAY_NAME) { $env:MONITORAPET_STORE_PUBLISHER_DISPLAY_NAME } else { $env:VIGIAPET_STORE_PUBLISHER_DISPLAY_NAME }),
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
