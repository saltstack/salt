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
$SCRIPTS_DIR    = "$BUILD_DIR\Scripts"
$BUILD_CONF_DIR = "$BUILD_DIR\configs"
$SITE_PKGS_DIR  = "$BUILD_DIR\Lib\site-packages"
$BUILD_SALT_DIR = "$SITE_PKGS_DIR\salt"
$PYTHON_BIN     = "$SCRIPTS_DIR\python.exe"
$PY_VERSION     = [Version]((Get-Command $PYTHON_BIN).FileVersionInfo.ProductVersion)
$PY_VERSION     = "$($PY_VERSION.Major).$($PY_VERSION.Minor)"
$ARCH           = $(. $PYTHON_BIN -c "import platform; print(platform.architecture()[0])")

if ( $ARCH -eq "64bit" ) {
    $ARCH         = "AMD64"
    $ARCH_X       = "x64"
    $SALT_DEP_URL = "https://repo.saltproject.io/windows/dependencies/64"
} else {
    $ARCH         = "x86"
    $ARCH_X       = "x86"
    $SALT_DEP_URL = "https://repo.saltproject.io/windows/dependencies/32"
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
    Write-Host "Copying SSM to Root: " -NoNewline
    Invoke-WebRequest -Uri "$SALT_DEP_URL/ssm-2.24-103-gdee49fc.exe" -OutFile "$BUILD_DIR\ssm.exe"
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
