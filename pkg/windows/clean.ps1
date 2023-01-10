<#
.SYNOPSIS
Clean the build environment

.DESCRIPTION
This script Cleans, Installs Dependencies, Builds Python, Installs Salt,
and builds the NullSoft Installer. It depends on the following Scripts
and are called in this order:

- clean_env.ps1
- install_nsis.ps1
- build_python.ps1
- install_salt.ps1
- build_pkg.ps1

.EXAMPLE
build.ps1

.EXAMPLE
build.ps1 -Version 3005 -PythonVersion 3.8.13

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

$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------

$SCRIPT_DIR   = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$RELENV_DIR   = "${env:LOCALAPPDATA}\relenv"

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

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------
Write-Host $("=" * 80)
Write-Host "Clean Build Environment" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Make sure we're not in a virtual environment
#-------------------------------------------------------------------------------
if ( $env:VIRTUAL_ENV ) {
    # I've tried deactivating from the script, but it doesn't work
    Write-Host "Please deactive the virtual environment"
    exit
}

#-------------------------------------------------------------------------------
# Remove venv directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
    Write-Host "Removing venv directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\venv" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove build directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\build" ) {
    Write-Host "Removing build directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\build" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\build" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove buildenv directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\buildenv" ) {
    Write-Host "Removing buildenv directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\buildenv" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\buildenv" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove prereqs directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\prereqs" ) {
    Write-Host "Removing prereqs directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\prereqs" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\prereqs" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove relenv local
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$RELENV_DIR" ) {
    Write-Host "Removing relenv directory: " -NoNewline
    Remove-Item -Path "$RELENV_DIR" -Recurse -Force
    if ( Test-Path -Path "$RELENV_DIR" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Script Completed
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "Clean Build Environment Completed" -ForegroundColor Cyan
Write-Host $("=" * 80)
