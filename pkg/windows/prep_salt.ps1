<#
.SYNOPSIS
Script that installs Salt into the Python environment

.DESCRIPTION
This script prepares the salt build directory for packaging by staging files
needed by the installer or zip file. It also removes unneeded execution and
state modules

It is after this script runs that we can create the ZipFile for the Onedir
builds

.EXAMPLE
prep_salt.ps1

#>
param(
    [Parameter(Mandatory=$false)]
    [Alias("b")]
    # Don't pretify the output of the Write-Result
    [String] $BuildDir,

    [Parameter(Mandatory=$false)]
    [Alias("c")]
    # Don't pretify the output of the Write-Result
    [Switch] $CICD,

    [Parameter(Mandatory=$false)]
    # When true, additional routines are done to prepare for packaging.
    [Switch] $PKG
)

#-------------------------------------------------------------------------------
# Script Preferences
#-------------------------------------------------------------------------------

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
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

$PROJECT_DIR    = $(git rev-parse --show-toplevel)
$SCRIPT_DIR     = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
if ( $BuildDir ) {
    $BUILD_DIR = $BuildDir
} else {
    $BUILD_DIR = "$SCRIPT_DIR\buildenv"
}
$PREREQ_DIR     = "$SCRIPT_DIR\prereqs"
$SCRIPTS_DIR    = "$BUILD_DIR\Scripts"
$BUILD_CONF_DIR = "$BUILD_DIR\configs"
$SITE_PKGS_DIR  = "$BUILD_DIR\Lib\site-packages"
$PYTHON_BIN     = "$SCRIPTS_DIR\python.exe"
$PY_VERSION     = [Version]((Get-Command $PYTHON_BIN).FileVersionInfo.ProductVersion)
$PY_VERSION     = "$($PY_VERSION.Major).$($PY_VERSION.Minor)"
$PY_ARCH        = $(. $PYTHON_BIN -c "import platform; print(platform.architecture()[0])")
$DEPS_URL       = "https://github.com/saltstack/salt-windows-deps/raw/refs/heads/main"

if ( $PY_ARCH -eq "64bit" ) {
    $ARCH         = "x64"
    $SSM_URL      = "$DEPS_URL/ssm/64/ssm-2.24-103-gdee49fc.exe"
    $VCREDIST_URL = "$DEPS_URL/vcredist"
} else {
    $ARCH         = "x86"
    $SSM_URL      = "$DEPS_URL/ssm/32/ssm-2.24-103-gdee49fc.exe"
    $VCREDIST_URL = "$DEPS_URL/vcredist"
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Prepare Salt for Packaging: " -ForegroundColor Cyan
Write-Host "- Architecture: $ARCH"
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Verify Environment
#-------------------------------------------------------------------------------

Write-Host "Verifying Python Build: " -NoNewline
if ( Test-Path -Path "$PYTHON_BIN" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Verifying Salt Installation: " -NoNewline
if ( Test-Path -Path "$BUILD_DIR\salt-minion.exe" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Cleaning Build Environment
#-------------------------------------------------------------------------------

if ( Test-Path -Path $BUILD_CONF_DIR) {
    Write-Host "Removing Configs Directory: " -NoNewline
    Remove-Item -Path $BUILD_CONF_DIR -Recurse -Force
    if ( ! (Test-Path -Path $BUILD_CONF_DIR) ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

if ( Test-Path -Path $PREREQ_DIR ) {
    Write-Host "Removing PreReq Directory: " -NoNewline
    Remove-Item -Path $PREREQ_DIR -Recurse -Force
    if ( ! (Test-Path -Path $PREREQ_DIR) ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Staging the Build Environment
#-------------------------------------------------------------------------------

if ( $PKG ) {
    Write-Host "Copying config files from Salt: " -NoNewline
    New-Item -Path $BUILD_CONF_DIR -ItemType Directory | Out-Null
    Copy-Item -Path "$PROJECT_DIR\conf\minion" -Destination "$BUILD_CONF_DIR"
    if ( Test-Path -Path "$BUILD_CONF_DIR\minion" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

# Make sure ssm.exe is present. This is needed for VMtools
if ( ! (Test-Path -Path "$BUILD_DIR\ssm.exe") ) {
    Write-Host "Copying SSM $ARCH to Root: " -NoNewline
    Invoke-WebRequest -Uri "$SSM_URL" -OutFile "$BUILD_DIR\ssm.exe"
    if ( Test-Path -Path "$BUILD_DIR\ssm.exe" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

# Copy the multiminion scripts to the Build directory
$scripts = @(
    "multi-minion.cmd",
    "multi-minion.ps1"
)
$scripts | ForEach-Object {
    if (!(Test-Path -Path "$BUILD_DIR\$_")) {
        Write-Host "Copying $_ to the Build directory: " -NoNewline
        Copy-Item -Path "$SCRIPT_DIR\$_" -Destination "$BUILD_DIR\$_"
        if (Test-Path -Path "$BUILD_DIR\$_") {
            Write-Result "Success" -ForegroundColor Green
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

# Copy VCRedist 2022 to the prereqs directory
New-Item -Path $PREREQ_DIR -ItemType Directory | Out-Null
Write-Host "Copying VCRedist 2022 $ARCH to prereqs: " -NoNewline
$file = "vcredist_$ARCH`_2022.exe"
Invoke-WebRequest -Uri "$VCREDIST_URL\$file" -OutFile "$PREREQ_DIR\$file"
if ( Test-Path -Path "$PREREQ_DIR\$file" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Remove binaries not needed by Salt
#-------------------------------------------------------------------------------

if ( $PKG ) {
    $binaries = @(
        "py.exe",
        "pyw.exe",
        "venvlauncher.exe",
        "venvwlauncher.exe"
    )
    Write-Host "Removing Python binaries: " -NoNewline
    $binaries | ForEach-Object {
        if ( Test-Path -Path "$SCRIPTS_DIR\$_" ) {
            # Use .net, the powershell function is asynchronous
            [System.IO.File]::Delete("$SCRIPTS_DIR\$_")
            if ( Test-Path -Path "$SCRIPTS_DIR\$_" ) {
                Write-Result "Failed" -ForegroundColor Red
                exit 1
            }
        }
    }
    Write-Result "Success" -ForegroundColor Green
}

#-------------------------------------------------------------------------------
# Remove pywin32 components not needed by Salt
#-------------------------------------------------------------------------------

$directories = "adodbapi",
               "isapi",
               "pythonwin",
               "win32\demos"
$directories | ForEach-Object {
    if ( Test-Path -Path "$SITE_PKGS_DIR\$_" ) {
        Write-Host "Removing $_ directory: " -NoNewline
        Remove-Item -Path "$SITE_PKGS_DIR\$_" -Recurse | Out-Null
        if ( ! (Test-Path -Path "$SITE_PKGS_DIR\$_") ) {
            Write-Result "Success" -ForegroundColor Green
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

#-------------------------------------------------------------------------------
# Remove pywin32 components not needed by Salt
#-------------------------------------------------------------------------------

$directories = "cheroot\test",
               "cherrypy\test",
               "gitdb\test",
               "psutil\tests",
               "smmap\test",
               "tempora\tests",
               "win32\test",
               "win32com\test",
               "zmq\tests"
$directories | ForEach-Object {
    if ( Test-Path -Path "$SITE_PKGS_DIR\$_" ) {
        Write-Host "Removing $_ directory: " -NoNewline
        Remove-Item -Path "$SITE_PKGS_DIR\$_" -Recurse | Out-Null
        if ( ! (Test-Path -Path "$SITE_PKGS_DIR\$_") ) {
            Write-Result "Success" -ForegroundColor Green
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

Write-Host "Removing unneeded files (.pyc, .chm): " -NoNewline
$remove = "__pycache__",
          "*.pyc",
          "*.chm"
$remove | ForEach-Object {
    $found = Get-ChildItem -Path "$BUILD_DIR\$_" -Recurse
    $found | ForEach-Object {
        Remove-Item -Path "$_" -Recurse -Force
        if ( Test-Path -Path $_ ) {
            Write-Result "Failed" -ForegroundColor Red
            Write-Host "Failed to remove: $_"
            exit 1
        }
    }
}
Write-Result "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "Prepare Salt for Packaging Complete" -ForegroundColor Cyan
Write-Host $("=" * 80)
