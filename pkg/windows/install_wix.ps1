<#
.SYNOPSIS
Script that installs the Wix Toolset

.DESCRIPTION
This script installs the Wix Toolset and it's dependency .Net Framework 3.5

.EXAMPLE
install_wix.ps1

#>
param(
    [Parameter(Mandatory=$false)]
    [Alias("c")]
    # Don't pretify the output of the Write-Result
    [Switch] $CICD
)

#-------------------------------------------------------------------------------
# Script Preferences
#-------------------------------------------------------------------------------

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Script Functions
#-------------------------------------------------------------------------------

function ProductcodeExists($productCode) {
    # Verify product code in registry
    Test-Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$productCode
}

function Write-Result($result, $ForegroundColor="Green") {
    if ( $CICD ) {
        Write-Host $result -ForegroundColor $ForegroundColor
    } else {
        $position = 80 - $result.Length - [System.Console]::CursorLeft
        Write-Host -ForegroundColor $ForegroundColor ("{0,$position}$result" -f "")
    }
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Install Wix Toolset" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# .Net Framework 3.5
#-------------------------------------------------------------------------------

Write-Host "Looking for .Net Framework 3.5: " -NoNewline
if ( (Get-WindowsOptionalFeature -Online -FeatureName "NetFx3").State -eq "Enabled" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow
    Write-Host "Installing .Net Framework 3.5: " -NoNewline
    Dism /online /enable-feature /featurename:NetFx3 /all
    if ( (Get-WindowsOptionalFeature -Online -FeatureName "NetFx3").State -eq "Enabled" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Wix Toolset
#-------------------------------------------------------------------------------

Write-Host "Looking for Wix Toolset: " -NoNewline
# 64bit: {03368010-193D-4AE2-B275-DD2EB32CD427}
# 32bit: {07188017-A460-4C0D-A386-6B3CEB8E20CD}
if ((ProductcodeExists "{03368010-193D-4AE2-B275-DD2EB32CD427}") `
    -or `
    (ProductcodeExists "{07188017-A460-4C0D-A386-6B3CEB8E20CD}")) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Downloading Wix Toolset: " -NoNewline
    $url = "https://github.com/wixtoolset/wix3/releases/download/wix3112rtm/wix311.exe"
    $file = "$env:TEMP\wix_installer.exe"
    Invoke-WebRequest -Uri $url -OutFile "$file"
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Installing Wix Toolset: " -NoNewline
    Start-Process $file -ArgumentList "/install","/quiet","/norestart" -Wait -NoNewWindow
    if ((ProductcodeExists "{03368010-193D-4AE2-B275-DD2EB32CD427}") `
    -or `
    (ProductcodeExists "{07188017-A460-4C0D-A386-6B3CEB8E20CD}")) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Cleaning up: " -NoNewline
    Remove-Item -Path $file -Force
    if ( ! (Test-Path -Path "$file") ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    }
}

Write-Host $("-" * 80)
Write-Host "Install Wix Toolset Completed" -ForegroundColor Cyan
Write-Host $("=" * 80)
