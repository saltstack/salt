<#
.SYNOPSIS
Install an OpenSSL development tree so arm64 Salt builds can compile
cryptography from source.

.DESCRIPTION
pyca/cryptography does not publish win_arm64 wheels on PyPI. When pip
installs Salt on a native arm64 Windows host, it falls back to the
cryptography sdist, which compiles the Rust openssl-sys crate. That
build script needs an OpenSSL installation on disk and the OPENSSL_DIR
environment variable pointing at it, and refuses to proceed otherwise.

This script provisions OpenSSL via vcpkg's prebuilt arm64-windows
triplet, exports OPENSSL_DIR / OPENSSL_INCLUDE_DIR / OPENSSL_LIB_DIR
machine-wide so the subsequent install_salt.ps1 pip-install picks them
up, and also writes them to GITHUB_ENV when running in CI so
subsequent GitHub Actions steps see them too.

On x86 / amd64 the script is a no-op because PyPI ships win_amd64
wheels for cryptography.

.EXAMPLE
install_openssl.ps1 -Architecture arm64 -CICD
#>
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("x86", "x64", "amd64", "arm64")]
    [Alias("a")]
    [String] $Architecture = "amd64",

    [Parameter(Mandatory=$false)]
    [Alias("c")]
    [Switch] $CICD
)

#-------------------------------------------------------------------------------
# Script Preferences
#-------------------------------------------------------------------------------

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Helpers
#-------------------------------------------------------------------------------

function Write-Result($result, $ForegroundColor="Green") {
    if ( $CICD ) {
        Write-Host $result -ForegroundColor $ForegroundColor
    } else {
        $position = 80 - $result.Length - [System.Console]::CursorLeft
        Write-Host -ForegroundColor $ForegroundColor ("{0,$position}$result" -f "")
    }
}

function Set-BuildEnv($Name, $Value) {
    # Persist for subsequent child processes in this build, and also hand
    # the value up to later GitHub Actions steps when running under CI.
    [Environment]::SetEnvironmentVariable($Name, $Value, 'Machine')
    [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
    if ( $CICD -and $env:GITHUB_ENV ) {
        Add-Content -Path $env:GITHUB_ENV -Value "$Name=$Value"
    }
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Install OpenSSL Development Headers" -ForegroundColor Cyan
Write-Host $("-" * 80)

# x86 / x64 / amd64: cryptography ships prebuilt win_amd64 wheels on PyPI,
# so no OpenSSL headers are needed.  Short-circuit cleanly.
if ( $Architecture -ne "arm64" ) {
    Write-Host "Skipping OpenSSL install for $Architecture (cryptography ships a prebuilt wheel on PyPI): " -NoNewline
    Write-Result "Not needed" -ForegroundColor Green
    Write-Host $("-" * 80)
    Write-Host "Install OpenSSL Development Headers Completed" -ForegroundColor Cyan
    Write-Host $("=" * 80)
    exit 0
}

#-------------------------------------------------------------------------------
# vcpkg Discovery
#-------------------------------------------------------------------------------

# Prefer whichever vcpkg the runner image already ships.  GitHub's
# windows-* images install vcpkg at $env:VCPKG_INSTALLATION_ROOT.
Write-Host "Locating vcpkg: " -NoNewline
$vcpkg_root = $null
foreach ( $candidate in @($env:VCPKG_ROOT, $env:VCPKG_INSTALLATION_ROOT, "C:\vcpkg") ) {
    if ( -not [String]::IsNullOrEmpty($candidate) -and (Test-Path -Path "$candidate\vcpkg.exe") ) {
        $vcpkg_root = $candidate
        break
    }
}
if ( $null -ne $vcpkg_root ) {
    Write-Result "Found: $vcpkg_root" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Cloning vcpkg: " -NoNewline
    $vcpkg_root = "$env:TEMP\vcpkg"
    if ( Test-Path -Path $vcpkg_root ) {
        Remove-Item -Path $vcpkg_root -Recurse -Force
    }
    & git clone --depth 1 https://github.com/microsoft/vcpkg $vcpkg_root 2>&1 | Out-Null
    if ( Test-Path -Path "$vcpkg_root\bootstrap-vcpkg.bat" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Bootstrapping vcpkg: " -NoNewline
    & "$vcpkg_root\bootstrap-vcpkg.bat" -disableMetrics 2>&1 | Out-Null
    if ( Test-Path -Path "$vcpkg_root\vcpkg.exe" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

$env:VCPKG_ROOT = $vcpkg_root

#-------------------------------------------------------------------------------
# Install OpenSSL for the arm64-windows triplet
#-------------------------------------------------------------------------------

$triplet = "arm64-windows"
$installed_dir = "$vcpkg_root\installed\$triplet"

Write-Host "Checking for existing OpenSSL ($triplet): " -NoNewline
if ( (Test-Path -Path "$installed_dir\include\openssl\ssl.h") -and `
     (Test-Path -Path "$installed_dir\lib\libssl.lib") ) {
    Write-Result "Found" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    # vcpkg's openssl port pulls in its own perl, no separate Strawberry
    # Perl install needed.  Cold build is ~15-20 minutes; CI caches
    # $vcpkg_root\installed between runs keyed on vcpkg's manifest hash.
    Write-Host "Installing OpenSSL via vcpkg (first run ~15 min; cached after): " -NoNewline
    $proc = Start-Process `
        -FilePath "$vcpkg_root\vcpkg.exe" `
        -ArgumentList "install", "openssl:$triplet", "--disable-metrics" `
        -NoNewWindow -Wait -PassThru
    if ( $proc.ExitCode -eq 0 -and (Test-Path -Path "$installed_dir\include\openssl\ssl.h") ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed (exit $($proc.ExitCode))" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Export environment variables for the pip-install step
#-------------------------------------------------------------------------------

# openssl-sys (the Rust crate cryptography compiles) probes several env
# vars in this order; setting all three is the most reliable combination
# across vcpkg's prebuilt layout and openssl-sys's build.rs expectations.
#   - OPENSSL_DIR: parent of include/ and lib/
#   - OPENSSL_INCLUDE_DIR: explicit header path (wins over OPENSSL_DIR)
#   - OPENSSL_LIB_DIR: explicit library path (wins over OPENSSL_DIR)
# The AARCH64_PC_WINDOWS_MSVC_OPENSSL_DIR variant is the target-prefixed
# form cargo probes first; set it too so we don't rely on target probing.
Write-Host "Exporting OPENSSL_* env vars: " -NoNewline
Set-BuildEnv "OPENSSL_DIR"           $installed_dir
Set-BuildEnv "OPENSSL_INCLUDE_DIR"   "$installed_dir\include"
Set-BuildEnv "OPENSSL_LIB_DIR"       "$installed_dir\lib"
Set-BuildEnv "AARCH64_PC_WINDOWS_MSVC_OPENSSL_DIR" $installed_dir
Write-Result "Success" -ForegroundColor Green

Write-Host "  OPENSSL_DIR         = $installed_dir"
Write-Host "  OPENSSL_INCLUDE_DIR = $installed_dir\include"
Write-Host "  OPENSSL_LIB_DIR     = $installed_dir\lib"

Write-Host $("-" * 80)
Write-Host "Install OpenSSL Development Headers Completed" -ForegroundColor Cyan
Write-Host $("=" * 80)
