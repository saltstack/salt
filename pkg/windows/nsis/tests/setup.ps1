<#
.SYNOPSIS
Script that sets up the environment for testing

.DESCRIPTION
This script creates the directory structure and files needed build a mock salt
installer for testing

.EXAMPLE
setup.ps1
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

$PROJECT_DIR   = $(git rev-parse --show-toplevel)
$SCRIPT_DIR    = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$WINDOWS_DIR   = "$PROJECT_DIR\pkg\windows"
$NSIS_DIR      = "$WINDOWS_DIR\nsis"
$BUILDENV_DIR  = "$WINDOWS_DIR\buildenv"
$NSIS_BIN      = "$( ${env:ProgramFiles(x86)} )\NSIS\makensis.exe"
$SALT_DEP_URL = "https://repo.saltproject.io/windows/dependencies/64"

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Build Test Environment for NSIS Tests" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Setup Directories
#-------------------------------------------------------------------------------

$directories = "$BUILDENV_DIR",
               "$BUILDENV_DIR\configs"
$directories | ForEach-Object {
    if ( ! (Test-Path -Path "$_") ) {
        Write-Host "Creating $_`: " -NoNewline
        New-Item -Path $_ -ItemType Directory | Out-Null
        if ( Test-Path -Path "$_" ) {
            Write-Result "Success"
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

#-------------------------------------------------------------------------------
# Create binaries
#-------------------------------------------------------------------------------

$binary_files = @("python.exe")
$binary_files | ForEach-Object {
    Write-Host "Creating $_`: " -NoNewline
    Set-Content -Path "$BUILDENV_DIR\$_" -Value "binary"
    if ( Test-Path -Path "$BUILDENV_DIR\$_" ) {
        Write-Result "Success"
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

# Make sure ssm.exe is present. This is needed for VMtools
if ( ! (Test-Path -Path "$BUILDENV_DIR\ssm.exe") ) {
    Write-Host "Copying SSM to Build Env: " -NoNewline
    Invoke-WebRequest -Uri "$SALT_DEP_URL/ssm-2.24-103-gdee49fc.exe" -OutFile "$BUILDENV_DIR\ssm.exe"
    if ( Test-Path -Path "$BUILDENV_DIR\ssm.exe" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Copy Configs
#-------------------------------------------------------------------------------

Write-Host "Copy testing minion config: " -NoNewline
Copy-Item -Path "$NSIS_DIR\tests\_files\minion" `
          -Destination "$BUILDENV_DIR\configs\"
if ( Test-Path -Path "$BUILDENV_DIR\configs\minion" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Build mock installer
#-------------------------------------------------------------------------------
Write-Host "Building mock installer: " -NoNewline
Start-Process -FilePath $NSIS_BIN `
              -ArgumentList "/DSaltVersion=test", `
                            "/DPythonArchitecture=AMD64", `
                            "$NSIS_DIR\installer\Salt-Minion-Setup.nsi" `
              -Wait -WindowStyle Hidden
$installer = "$NSIS_DIR\installer\Salt-Minion-test-Py3-AMD64-Setup.exe"
if ( Test-Path -Path "$installer" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    Write-Host "$NSIS_BIN /DSaltVersion=test /DPythonArchitecture=AMD64 $NSIS_DIR\installer\Salt-Minion-Setup.nsi"
    exit 1
}

Write-Host "Moving mock installer: " -NoNewline
$test_installer = "$NSIS_DIR\tests\test-setup.exe"
Move-Item -Path $installer -Destination "$test_installer" -Force
if ( Test-Path -Path "$test_installer" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Setup pytest
#-------------------------------------------------------------------------------

Write-Host "Setting up venv: " -NoNewline
python.exe -m venv "$SCRIPT_DIR\venv"
if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Activating venv: " -NoNewline
& $SCRIPT_DIR\venv\Scripts\activate.ps1
if ( "$env:VIRTUAL_ENV" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

$pip_modules = "pytest",
               "pytest-helpers-namespace",
               "psutil"
$pip_modules | ForEach-Object {
    Write-Host "Installing $_`: " -NoNewline
    Start-Process -FilePath pip `
                  -ArgumentList "install", "$_" `
                  -Wait -WindowStyle Hidden
    if ($( pip show $_ ) -contains "Name: $_") {
        Write-Result "Success"
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Build Test Environment for NSIS Tests Complete" -ForegroundColor Cyan
Write-Host $("=" * 80)
