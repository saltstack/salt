<#
.SYNOPSIS
Script that builds Python from source using the Relative Environment for Python
project (relenv):

https://github.com/saltstack/relative-environment-for-python

.DESCRIPTION
This script builds python from Source. It then creates the directory structure
as created by the Python installer. This includes all header files, scripts,
dlls, library files, and pip.

.EXAMPLE
build_python.ps1 -Version 3.10.9 -Architecture x86

#>
param(
    [Parameter(Mandatory=$false)]
    [ValidatePattern("^\d{1,2}.\d{1,2}.\d{1,2}$")]
    [ValidateSet(
        "3.11.2",
        "3.10.10"
    )]
    [Alias("v")]
    # The version of Python to be built. Pythonnet only supports up to Python
    # 3.8 for now. Pycurl stopped building wheel files after 7.43.0.5 which
    # supported up to 3.8. So we're pinned to the latest version of Python 3.8.
    # We may have to drop support for pycurl or build it ourselves.
    # Default is: 3.8.16
    [String] $Version = "3.10.10",

    [Parameter(Mandatory=$false)]
    [ValidateSet("x64", "x86", "amd64")]
    [Alias("a")]
    # The System Architecture to build. "x86" will build a 32-bit installer.
    # "x64" will build a 64-bit installer. Default is: x64
    [String] $Architecture = "x64",

    [Parameter(Mandatory=$false)]
    [Alias("b")]
    # Build python from source instead of fetching a tarball
    # Requires VC Build Tools
    [Switch] $Build,

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

if ( $Architecture -eq "amd64" ) {
  $Architecture = "x64"
}

#-------------------------------------------------------------------------------
# Script Functions
#-------------------------------------------------------------------------------

function Write-Result($result, $ForegroundColor="Green") {
    if ( $CICD ) {
        Write-Host $result -ForegroundColor $ForegroundColor
    } else {
        $position = 80 - $result.Length - [System.Console]::CursorLeft
        Write-Host -ForegroundColor $ForegroundColor ("{0,$position}$result" -f "")
    }}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
if ( $Build ) {
    $SCRIPT_MSG = "Build Python with Relenv"
} else {
    $SCRIPT_MSG = "Fetch Python with Relenv"
}
Write-Host "$SCRIPT_MSG" -ForegroundColor Cyan
Write-Host "- Python Version: $Version"
Write-Host "- Architecture:   $Architecture"
Write-Host "- Build:          $Build"
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
            Write-Result "Success" -ForegroundColor Green
        } else {
            Write-Result "Failed" -ForegroundColor Red
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
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Creating Temporary PowerShell Profile: " -NoNewline
'$ProgressPreference = "SilentlyContinue"' | Out-File -FilePath $profile
'$ErrorActionPreference = "Stop"' | Out-File -FilePath $profile
Write-Result "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Make sure we're not in a virtual environment
#-------------------------------------------------------------------------------
if ( $env:VIRTUAL_ENV ) {
    Write-Host "Deactivating virtual environment"
    . deactivate
    Write-Host $env:VIRTUAL_ENV
    if ( $env:VIRTUAL_ENV ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------
$SCRIPT_DIR   = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$BUILD_DIR    = "$SCRIPT_DIR\buildenv"
$SCRIPTS_DIR  = "$BUILD_DIR\Scripts"
$RELENV_DIR   = "${env:LOCALAPPDATA}\relenv"
$SYS_PY_BIN   = (python -c "import sys; print(sys.executable)")
$BLD_PY_BIN   = "$BUILD_DIR\Scripts\python.exe"
$SALT_DEP_URL = "https://repo.saltproject.io/windows/dependencies"

if ( $Architecture -eq "x64" ) {
    $SALT_DEP_URL = "$SALT_DEP_URL/64"
    $ARCH         = "amd64"
} else {
    $SALT_DEP_URL = "$SALT_DEP_URL/32"
    $ARCH         = "x86"
}

#-------------------------------------------------------------------------------
# Prepping Environment
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
    Write-Host "Removing virtual environment directory: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\venv" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

if ( Test-Path -Path "$RELENV_DIR" ) {
    Write-Host "Removing existing relenv directory: " -NoNewline
    Remove-Item -Path "$RELENV_DIR" -Recurse -Force
    if ( Test-Path -Path "$RELENV_DIR" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

if ( Test-Path -Path "$BUILD_DIR" ) {
    Write-Host "Removing existing build directory: " -NoNewline
    Remove-Item -Path "$BUILD_DIR" -Recurse -Force
    if ( Test-Path -Path "$BUILD_DIR" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Setting Up Virtual Environment
#-------------------------------------------------------------------------------
Write-Host "Installing virtual environment: " -NoNewline
Start-Process -FilePath "$SYS_PY_BIN" `
              -ArgumentList "-m", "venv", "venv" `
              -WorkingDirectory "$SCRIPT_DIR" `
              -Wait -WindowStyle Hidden
if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed"
    exit 1
}

Write-Host "Activating virtual environment: " -NoNewline
. "$SCRIPT_DIR\venv\Scripts\activate.ps1"
if ( $env:VIRTUAL_ENV ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Installing Relenv
#-------------------------------------------------------------------------------
Write-Host "Installing Relenv: " -NoNewLine
pip install relenv --disable-pip-version-check | Out-Null
$output = pip list --disable-pip-version-check
if ("relenv" -in $output.split()) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Building Python with Relenv
#-------------------------------------------------------------------------------
if ( $Build ) {
    Write-Host "Building Python with Relenv (long-running): " -NoNewLine
    $output = relenv build --clean --arch $ARCH
} else {
    Write-Host "Fetching Python with Relenv: " -NoNewLine
    relenv fetch --python $Version --arch $ARCH | Out-Null
}
if ( Test-Path -Path "$RELENV_DIR\build\$Version-$ARCH-win.tar.xz") {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Extracting Python environment
#-------------------------------------------------------------------------------
Write-Host "Extracting Python environment: " -NoNewLine
relenv create --python $Version --arch $ARCH "$BUILD_DIR"
If ( Test-Path -Path "$BLD_PY_BIN" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Retrieving SSL Libraries
#-------------------------------------------------------------------------------
$ssllibs = "libeay32.dll",
           "ssleay32.dll"
$ssllibs | ForEach-Object {
    $url = "$SALT_DEP_URL/openssl/1.1.1s/$_"
    $file = "$SCRIPTS_DIR\$_"
    Write-Host "Retrieving $_`: " -NoNewline
    Invoke-WebRequest -Uri "$url" -OutFile "$file" | Out-Null
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Removing Unneeded files from Python
#-------------------------------------------------------------------------------
$remove = "idlelib",
          "test",
          "tkinter",
          "turtledemo"
$remove | ForEach-Object {
    if ( Test-Path -Path "$BUILD_DIR\Lib\$_" ) {
        Write-Host "Removing $_`: " -NoNewline
        Remove-Item -Path "$BUILD_DIR\Lib\$_" -Recurse -Force
        if (Test-Path -Path "$BUILD_DIR\Lib\$_") {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        } else {
            Write-Result "Success" -ForegroundColor Green
        }
    }
}

#-------------------------------------------------------------------------------
# Restoring Original Global Script Preferences
#-------------------------------------------------------------------------------
if ( $CREATED_POWERSHELL_PROFILE_DIRECTORY ) {
    Write-Host "Removing PowerShell Profile Directory: " -NoNewline
    Remove-Item -Path "$(Split-Path "$profile" -Parent)" -Recurse -Force
    if ( !  (Test-Path -Path "$(Split-Path "$profile" -Parent)") ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failure" -ForegroundColor Red
        exit 1
    }
}

if ( Test-Path -Path "$profile" ) {
    Write-Host "Removing Temporary PowerShell Profile: " -NoNewline
    Remove-Item -Path "$profile" -Force
    if ( ! (Test-Path -Path "$profile") ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

if ( Test-Path -Path "$profile.salt_bak" ) {
    Write-Host "Restoring Original PowerShell Profile: " -NoNewline
    Move-Item -Path "$profile.salt_bak" -Destination "$profile"
    if ( Test-Path -Path "$profile" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "$SCRIPT_MSG Completed" -ForegroundColor Cyan
Write-Host "Environment Location: $BUILD_DIR"
Write-Host $("=" * 80)
