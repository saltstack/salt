<#
.SYNOPSIS
Script that installs Visual Studio Build Tools

.DESCRIPTION
This script installs the Visual Studio Build Tools if they are not already
present on the system. Visual Studio Build Tools are the binaries and libraries
needed to build Python from source.

.EXAMPLE
install_vc_buildtools.ps1

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
# https://stackoverflow.com/a/67201331/4581998
$env:PSModulePath = [Environment]::GetEnvironmentVariable('PSModulePath', 'Machine')

#-------------------------------------------------------------------------------
# Script Functions
#-------------------------------------------------------------------------------

function Write-Result($result, $ForegroundColor="Green") {
    if ( $CICD ) {
        Write-Host $result -ForegroundColor $ForegroundColor
    } else {
        $position = 80 - $result.Length - [System.Console]::CursorLeft
        Write-Host -ForegroundColor $ForegroundColor ("{0,$position}$result" -f "")
    }
}

function Add-Certificate {
    [CmdletBinding()]
    param(

        [Parameter(Mandatory=$true)]
        # The path in the certstore (CERT:/LocalMachine/Root/<hash>)
        [String] $Path,

        [Parameter(Mandatory=$true)]
        # The path to the cert file for importing
        [String] $File,

        [Parameter(Mandatory=$true)]
        # The name of the cert file for importing
        [String] $Name

    )

    # Validation
    if ( ! (Test-Path -Path $File)) {
        Write-Host "Invalid path to certificate file"
        exit 1
    }

    if (! (Test-Path -Path $Path) ) {

        Write-Host "Installing Certificate $Name`: " -NoNewLine
        $output = Import-Certificate -FilePath $File -CertStoreLocation "Cert:\LocalMachine\Root"
        if ( Test-Path -Path $Path ) {
            Write-Result "Success"
        } else {
            Write-Result "Failed" -ForegroundColor Yellow
            Write-Host $output
        }
    }
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Install Visual Studio Build Tools" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------

# Dependency Variables
$VS_BLD_TOOLS   = "https://aka.ms/vs/15/release/vs_buildtools.exe"
try {
    # If VS is installed, you will be able to get the WMI Object MSFT_VSInstance
    $VS_INST_LOC    = $(Get-CimInstance MSFT_VSInstance -Namespace root/cimv2/vs).InstallLocation
    $MSBUILD_BIN = $(Get-ChildItem "$VS_INST_LOC\MSBuild\*\Bin\msbuild.exe").FullName
} catch {
    # If VS is not installed, this is the fallback for this installation
    $MSBUILD_BIN    = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2017\BuildTools\MSBuild\15.0\Bin\msbuild.exe"
}

#-------------------------------------------------------------------------------
# Visual Studio
#-------------------------------------------------------------------------------

Write-Host "Confirming Presence of Visual Studio Build Tools: " -NoNewline
# We're only gonna look for msbuild.exe
if ( Test-Path -Path $MSBUILD_BIN ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    try {
        # If VS is installed, you will be able to get the WMI Object MSFT_VSInstance
        Write-Host "Get VS Instance Information"
        Get-CimInstance MSFT_VSInstance -Namespace root/cimv2/vs
    } catch {}

    Write-Host "Checking available disk space: " -NoNewLine
    $available = (Get-PSDrive $env:SystemDrive.Trim(":")).Free
    if ( $available -gt (1024 * 1024 * 1024 * 9.1) ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        Write-Host "Not enough disk space"
        exit 1
    }

    Write-Host "Downloading Visual Studio 2017 build tools: " -NoNewline
    Invoke-WebRequest -Uri "$VS_BLD_TOOLS" -OutFile "$env:TEMP\vs_buildtools.exe"
    if ( Test-Path -Path "$env:TEMP\vs_buildtools.exe" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Creating Layout for Visual Studio 2017 build tools: " -NoNewline
    if ( ! (Test-Path -Path "$($env:TEMP)\build_tools") ) {
        New-Item -Path "$($env:TEMP)\build_tools" -ItemType Directory | Out-Null
    }

    Start-Process -FilePath "$env:TEMP\vs_buildtools.exe" `
                  -ArgumentList "--layout `"$env:TEMP\build_tools`"", `
                                "--add Microsoft.VisualStudio.Workload.MSBuildTools", `
                                "--add Microsoft.VisualStudio.Workload.VCTools", `
                                "--add Microsoft.VisualStudio.Component.Windows81SDK", `
                                "--add Microsoft.VisualStudio.Component.VC.140", `
                                "--lang en-US", `
                                "--includeRecommended", `
                                "--quiet", `
                                "--wait" `
                  -Wait -WindowStyle Hidden
    if ( Test-Path -Path "$env:TEMP\build_tools\vs_buildtools.exe" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    # Serial: 28cc3a25bfba44ac449a9b586b4339aa
    # Hash: 3b1efd3a66ea28b16697394703a72ca340a05bd5
    $cert_name = "Sign Root Certificate"
    $cert_path = "Cert:\LocalMachine\Root\3b1efd3a66ea28b16697394703a72ca340a05bd5"
    $cert_file = "$env:TEMP\build_tools\certificates\manifestCounterSignRootCertificate.cer"
    Add-Certificate -Name $cert_name -Path $cert_path -File $cert_file

    # Serial: 3f8bc8b5fc9fb29643b569d66c42e144
    # Hash: 8f43288ad272f3103b6fb1428485ea3014c0bcfe
    $cert_name = "Root Certificate"
    $cert_path = "Cert:\LocalMachine\Root\8f43288ad272f3103b6fb1428485ea3014c0bcfe"
    $cert_file = "$env:TEMP\build_tools\certificates\manifestRootCertificate.cer"
    Add-Certificate -Name $cert_name -Path $cert_path -File $cert_file

    Write-Host "Installing Visual Studio 2017 build tools: " -NoNewline
    $proc = Start-Process `
        -FilePath "$env:TEMP\build_tools\vs_setup.exe" `
        -ArgumentList "--wait", "--noweb", "--quiet" `
        -PassThru -Wait `
        -RedirectStandardOutput "$env:TEMP\stdout.txt"
    if ( Test-Path -Path $MSBUILD_BIN ) {
        Write-Result "Failed" -ForegroundColor Red
        Write-Host "Missing: $_"
        Write-Host "ExitCode: $($proc.ExitCode)"
        Write-Host "STDOUT:"
        Get-Content "$env:TEMP\stdout.txt"
        exit 1
    }
    Write-Result "Success" -ForegroundColor Green
}

#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Install Visual Studio Build Tools Completed" -ForegroundColor Cyan
Write-Host $("=" * 80)
