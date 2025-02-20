<#
.SYNOPSIS
Script to run the tests

.DESCRIPTION
This script activates the venv and launches pytest

.EXAMPLE
test.ps1
#>
param(
    [Parameter(Mandatory=$false)]
    [Alias("c")]
# Don't pretify the output of the Write-Result
    [Switch] $CICD=$false,

    [Parameter(Mandatory=$false, ValueFromRemainingArguments=$true)]
# Don't pretify the output of the Write-Result
    [String]$Tests
)

#-------------------------------------------------------------------------------
# Script Preferences
#-------------------------------------------------------------------------------

$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

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
# Script Variables
#-------------------------------------------------------------------------------

$SCRIPT_DIR    = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Run Tests" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Activating venv
#-------------------------------------------------------------------------------
if ( !(Test-Path -Path "$SCRIPT_DIR\venv\Scripts\activate.ps1") ) {
    Write-Host "Could not find virtual environment"
    Write-Host "You must run setup.cmd before running this script"
}

Write-Host "Activating venv: " -NoNewline
& $SCRIPT_DIR\venv\Scripts\activate.ps1
if ( "$env:VIRTUAL_ENV" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Setting working directory: " -NoNewline
Set-Location -Path $SCRIPT_DIR
if ( $(Get-Location).Path -eq $SCRIPT_DIR ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host $("-" * 80)
Write-Host ""
Write-Host "Running pytest..."
Write-Host ""

if ($Tests) {
    $pytest_args = -join $Tests
} else {
    $pytest_args = ".\config_tests\"
}

pytest -vvv -rPx --showlocals -- $pytest_args

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Run Tests" -ForegroundColor Cyan
Write-Host $("=" * 80)
