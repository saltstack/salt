﻿<#
.SYNOPSIS
Script that builds Python from source using the Relative Environment for Python
project (relenv):

https://github.com/saltstack/relative-environment-for-python

.DESCRIPTION
This script builds python from Source. It then creates the directory structure
as created by the Python installer. This includes all header files, scripts,
dlls, library files, and pip.

.EXAMPLE
build_python.ps1 -Version 3.8.14 -Architecture x86

#>
param(
    [Parameter(Mandatory=$false)]
    [ValidatePattern("^\d{1,2}.\d{1,2}.\d{1,2}$")]
    [ValidateSet(
        #"3.10.5",
        #"3.10.4",
        #"3.10.3",
        #"3.9.13",
        #"3.9.12",
        #"3.9.11",
        "3.8.15",
        "3.8.14",
        "3.8.13",
        "3.8.12",
        "3.8.11",
        "3.8.10"
    )]
    [Alias("v")]
    # The version of Python to be built. Pythonnet only supports up to Python
    # 3.8 for now. Pycurl stopped building wheel files after 7.43.0.5 which
    # supported up to 3.8. So we're pinned to the latest version of Python 3.8.
    # We may have to drop support for pycurl or build it ourselves.
    # Default is: 3.8.15
    [String] $Version = "3.8.15",

    [Parameter(Mandatory=$false)]
    [ValidateSet("x64", "x86")]
    [Alias("a")]
    # The System Architecture to build. "x86" will build a 32-bit installer.
    # "x64" will build a 64-bit installer. Default is: x64
    $Architecture = "x64"
)

# Script Preferences
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Import Modules
#-------------------------------------------------------------------------------
$SCRIPT_DIR = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
Import-Module $SCRIPT_DIR\Modules\uac-module.psm1

#-------------------------------------------------------------------------------
# Check for Elevated Privileges
#-------------------------------------------------------------------------------
If (!(Get-IsAdministrator)) {
    If (Get-IsUacEnabled) {
        # We are not running "as Administrator" - so relaunch as administrator
        # Create a new process object that starts PowerShell
        $newProcess = new-object System.Diagnostics.ProcessStartInfo "PowerShell";

        # Specify the current script path and name as a parameter
        $newProcess.Arguments = $myInvocation.MyCommand.Definition

        # Specify the current working directory
        $newProcess.WorkingDirectory = "$SCRIPT_DIR"

        # Indicate that the process should be elevated
        $newProcess.Verb = "runas";

        # Start the new process
        [System.Diagnostics.Process]::Start($newProcess);

        # Exit from the current, unelevated, process
        Exit
    } Else {
        Throw "You must be administrator to run this script"
    }
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Build Python with Relenv" -ForegroundColor Cyan
Write-Host "- Python Version: $Version"
Write-Host "- Architecture:   $Architecture"
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Global Script Preferences
#-------------------------------------------------------------------------------
# The Python Build script doesn't disable the progress bar. This is a problem
# when trying to add this to CICD so we need to disable it system wide. This
# Adds $ProgressPreference=$false to the Default PowerShell profile so when the
# cpython build script is launched it will not display the progress bar. This
# file will be backed up if it already exists and will be restored at the end
# this script.
if ( Test-Path -Path "$profile" ) {
    if ( ! (Test-Path -Path "$profile.salt_bak") ) {
        Write-Host "Backing up PowerShell Profile: " -NoNewline
        Move-Item -Path "$profile" -Destination "$profile.salt_bak"
        if ( Test-Path -Path "$profile.salt_bak" ) {
            Write-Host "Success" -ForegroundColor Green
        } else {
            Write-Host "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

$CREATED_POWERSHELL_PROFILE_DIRECTORY = $false
if ( ! (Test-Path -Path "$(Split-Path "$profile" -Parent)") ) {
    Write-Host "Creating WindowsPowerShell Directory: " -NoNewline
    New-Item -Path "$(Split-Path "$profile" -Parent)" -ItemType Directory | Out-Null
    if ( Test-Path -Path "$(Split-Path "$profile" -Parent)" ) {
        $CREATED_POWERSHELL_PROFILE_DIRECTORY = $true
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Creating Temporary PowerShell Profile: " -NoNewline
'$ProgressPreference = "SilentlyContinue"' | Out-File -FilePath $profile
'$ErrorActionPreference = "Stop"' | Out-File -FilePath $profile
Write-Host "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------

$RELENV_DIR   = "$SCRIPT_DIR\relative-environment-for-python"
$RELENV_URL   = "https://github.com/saltstack/relative-environment-for-python"
$BIN_DIR      = "$SCRIPT_DIR\buildenv\bin"
$SCRIPTS_DIR  = "$BIN_DIR\Scripts"
$BUILD_DIR    = "${env:LOCALAPPDATA}\relenv\build"
$SALT_DEP_URL = "https://repo.saltproject.io/windows/dependencies"

if ( $Architecture -eq "x64" ) {
    $SALT_DEP_URL = "$SALT_DEP_URL/64"
    $BUILD_DIR    = "$BUILD_DIR\amd64-win"
    $ARCH         = "amd64"
} else {
    $SALT_DEP_URL = "$SALT_DEP_URL/32"
    $BUILD_DIR    = "$BUILD_DIR\x86-win"
    $ARCH         = "x86"
}

#-------------------------------------------------------------------------------
# Prepping Environment
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$RELENV_DIR" ) {
    Write-Host "Removing existing relenv directory: " -NoNewline
    Remove-Item -Path "$RELENV_DIR" -Recurse -Force
    if ( Test-Path -Path "$RELENV_DIR" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

if ( Test-Path -Path "$BIN_DIR" ) {
    Write-Host "Removing existing bin directory: " -NoNewline
    Remove-Item -Path "$BIN_DIR" -Recurse -Force
    if ( Test-Path -Path "$BIN_DIR" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

if ( Test-Path -Path "$BUILD_DIR" ) {
    Write-Host "Removing existing build directory: " -NoNewline
    Remove-Item -Path "$BUILD_DIR" -Recurse -Force
    if ( Test-Path -Path "$BUILD_DIR" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Downloading Relenv
#-------------------------------------------------------------------------------
# TODO: Eventually we should just download the tarball from a release, but since
# TODO: there is no release yet, we'll just clone the directory

Write-Host "Cloning Relenv: " -NoNewline
$args = "clone", "--depth", "1", "$RELENV_URL", "$RELENV_DIR"
Start-Process -FilePath git `
              -ArgumentList $args `
              -Wait -WindowStyle Hidden
if ( Test-Path -Path "$RELENV_DIR\relenv") {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Installing Relenv
#-------------------------------------------------------------------------------
Write-Host "Installing Relenv: " -NoNewLine
$output = pip install -e "$RELENV_DIR\." --disable-pip-version-check
$output = pip list --disable-pip-version-check
if ("relenv" -in $output.split()) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Building Python with Relenv
#-------------------------------------------------------------------------------
Write-Host "Building Python with Relenv (long-running): " -NoNewLine
$output = python -m relenv build --clean --arch $ARCH
if ( Test-Path -Path "$BUILD_DIR\Scripts\python.exe") {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Moving Python to Bin Dir
#-------------------------------------------------------------------------------
if ( !( Test-Path -Path $BIN_DIR ) ) {
    Write-Host "Creating the bin directory: " -NoNewLine
    New-Item -Path $BIN_DIR -ItemType Directory | Out-Null
    if ( Test-Path -Path $BIN_DIR ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Moving Python to bin: " -NoNewLine
Move-Item -Path "$BUILD_DIR\*" -Destination "$BIN_DIR"
if ( Test-Path -Path "$SCRIPTS_DIR\python.exe") {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Retrieving SSL Libraries
#-------------------------------------------------------------------------------
Write-Host "Retrieving SSL Libaries: " -NoNewline
$libeay_url = "$SALT_DEP_URL/openssl/1.1.1k/libeay32.dll"
$ssleay_url = "$SALT_DEP_URL/openssl/1.1.1k/ssleay32.dll"
Invoke-WebRequest -Uri "$libeay_url" -OutFile "$SCRIPTS_DIR\libeay32.dll" | Out-Null
Invoke-WebRequest -Uri "$ssleay_url" -OutFile "$SCRIPTS_DIR\ssleay32.dll" | Out-Null
if ( ! (Test-Path -Path "$SCRIPTS_DIR\libeay32.dll") ) {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}
if ( Test-Path -Path "$SCRIPTS_DIR\ssleay32.dll" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Removing Unneeded files from Python
#-------------------------------------------------------------------------------
Write-Host "Removing Unneeded Files from Python: " -NoNewline
$remove = "idlelib",
          "test",
          "tkinter",
          "turtledemo"
$remove | ForEach-Object {
    Remove-Item -Path "$BIN_DIR\Lib\$_" -Recurse -Force
    if ( Test-Path -Path "$BIN_DIR\Lib\$_" ) {
        Write-Host "Failed" -ForegroundColor Red
        Write-Host "Failed to remove: $BIN_DIR\Lib\$_"
        exit 1
    }
}
Write-Host "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Restoring Original Global Script Preferences
#-------------------------------------------------------------------------------
if ( $CREATED_POWERSHELL_PROFILE_DIRECTORY ) {
    Write-Host "Removing PowerShell Profile Directory"
    Remove-Item -Path "$(Split-Path "$profile" -Parent)" -Recurse -Force
    if ( !  (Test-Path -Path "$(Split-Path "$profile" -Parent)") ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failure" -ForegroundColor Red
        exit 1
    }
}

if ( Test-Path -Path "$profile" ) {
    Write-Host "Removing Temporary PowerShell Profile: " -NoNewline
    Remove-Item -Path "$profile" -Force
    if ( ! (Test-Path -Path "$profile") ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

if ( Test-Path -Path "$profile.salt_bak" ) {
    Write-Host "Restoring Original PowerShell Profile: " -NoNewline
    Move-Item -Path "$profile.salt_bak" -Destination "$profile"
    if ( Test-Path -Path "$profile" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "Build Python $Architecture with Relenv Completed" `
    -ForegroundColor Cyan
Write-Host "Environment Location: $BIN_DIR"
Write-Host $("=" * 80)
