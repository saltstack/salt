<#
.SYNOPSIS
Script to run the tests

.DESCRIPTION
This script activates the venv and launches pytest

.EXAMPLE
test.ps1
#>

#-------------------------------------------------------------------------------
# Script Preferences
#-------------------------------------------------------------------------------

$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Script Functions
#-------------------------------------------------------------------------------

function Write-Result($result, $ForegroundColor="Green") {
    $position = 80 - $result.Length - [System.Console]::CursorLeft
    Write-Host -ForegroundColor $ForegroundColor ("{0,$position}$result" -f "")
}

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Run Tests" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Activating venv
#-------------------------------------------------------------------------------

Write-Host "Activating venv: " -NoNewline
.\venv\Scripts\activate
if ( "$env:VIRTUAL_ENV" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Running pytest..."
Write-Host ""
pytest -vvv -- .\config_tests\

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Run Tests" -ForegroundColor Cyan
Write-Host $("=" * 80)
