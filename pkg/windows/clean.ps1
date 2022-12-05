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

# Script Preferences
$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
$SCRIPT_DIR   = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$RELENV_DIR   = "${env:LOCALAPPDATA}\relenv"

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
    Write-Host "Deactivating virtual environment: "
    & deactivate
    Write-Host $env:VIRTUAL_ENV
    if ( $env:VIRTUAL_ENV ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove venv directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
    Write-Host "Removing venv directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\venv" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove build directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\build" ) {
    Write-Host "Removing build directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\build" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\build" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove buildenv directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\buildenv" ) {
    Write-Host "Removing buildenv directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\buildenv" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\buildenv" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove prereqs directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\prereqs" ) {
    Write-Host "Removing prereqs directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\prereqs" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\prereqs" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove relenv local
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$RELENV_DIR" ) {
    Write-Host "Removing relenv directory: " -NoNewline
    Remove-Item -Path "$RELENV_DIR" -Recurse -Force
    if ( Test-Path -Path "$RELENV_DIR" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Script Completed
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "Clean Build Environment Completed" -ForegroundColor Cyan
Write-Host $("=" * 80)
