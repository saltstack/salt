<#
.SYNOPSIS
Clean the NSIS Tests directory

.DESCRIPTION
This script removes the venv directory and the test-setup.exe

.EXAMPLE
clean.ps1

.EXAMPLE
clean.ps1

#>

# Script Preferences
$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------

$SCRIPT_DIR   = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName

#-------------------------------------------------------------------------------
# Script Functions
#-------------------------------------------------------------------------------

function Write-Result($result, $ForegroundColor="Green") {
    $position = 80 - $result.Length - [System.Console]::CursorLeft
    Write-Host -ForegroundColor $ForegroundColor ("{0,$position}$result" -f "")
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------
Write-Host $("=" * 80)
Write-Host "Clean NSIS Test Environment" -ForegroundColor Cyan
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
# Remove test-setup.exe
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\test-setup.exe" ) {
    Write-Host "Removing test-setup.exe: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\test-setup.exe" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\test-setup.exe" ) {
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
Write-Host "Clean NSIS Test Environment Completed" -ForegroundColor Cyan
Write-Host $("=" * 80)
