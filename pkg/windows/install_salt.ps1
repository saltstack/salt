<#
.SYNOPSIS
Script that installs Salt in the Python environment

.DESCRIPTION
This script installs Salt into the Python environment built by the
build_python.ps1 script. It puts required dlls in the Python directory
and removes items not needed by a Salt installation on Windows such as Python
docs and test files. Once this script completes, the Python directory is
ready to be packaged.

.EXAMPLE
install_salt.ps1

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
    # Don't install. It should already be installed
    [Switch] $SkipInstall,

    [Parameter(Mandatory=$false)]
    # Path to a Salt source tarball which be used to install Salt.
    [String] $SourceTarball,

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

# Python Variables
$SCRIPT_DIR    = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
if ( $BuildDir ) {
    $BUILD_DIR = $BuildDir
} else {
    $BUILD_DIR = "$SCRIPT_DIR\buildenv"
}
$SITE_PKGS_DIR = "$BUILD_DIR\Lib\site-packages"
$SCRIPTS_DIR   = "$BUILD_DIR\Scripts"
$PYTHON_BIN    = "$SCRIPTS_DIR\python.exe"
$PY_VERSION    = [Version]((Get-Command $PYTHON_BIN).FileVersionInfo.ProductVersion)
$PY_MAJOR_VERSION = "$($PY_VERSION.Major)"
$PY_MINOR_VERSION = "$($PY_VERSION.Minor)"
$PY_VERSION    = "$($PY_VERSION.Major).$($PY_VERSION.Minor)"
$ARCH          = $(. $PYTHON_BIN -c "import platform; print(platform.architecture()[0])")

# Script Variables
$PROJECT_DIR     = $(git rev-parse --show-toplevel)
$SALT_DEPS       = "$PROJECT_DIR\requirements\static\pkg\py$PY_VERSION\windows.txt"
if ( $ARCH -eq "64bit" ) {
    $SALT_DEP_URL   = "https://repo.saltproject.io/windows/dependencies/64"
} else {
    $SALT_DEP_URL   = "https://repo.saltproject.io/windows/dependencies/32"
}

if ( ! $SkipInstall ) {
  #-------------------------------------------------------------------------------
  # Start the Script
  #-------------------------------------------------------------------------------
  Write-Host $("=" * 80)
  Write-Host "Install Salt into Python Environment" -ForegroundColor Cyan
  Write-Host "- Architecture: $ARCH"
  Write-Host $("-" * 80)

  #-------------------------------------------------------------------------------
  # Installing Salt
  #-------------------------------------------------------------------------------
  # We don't want to use an existing salt installation because we don't know what
  # it is
  Write-Host "Checking for existing Salt installation: " -NoNewline
  if ( ! (Test-Path -Path "$SCRIPTS_DIR\salt-minion.exe") ) {
      Write-Result "Success" -ForegroundColor Green
  } else {
      Write-Result "Failed" -ForegroundColor Red
      exit 1
  }

  # Cleaning previous builds
  $remove = "build", "dist"
  $remove | ForEach-Object {
      if ( Test-Path -Path "$PROJECT_DIR\$_" ) {
          Write-Host "Removing $_`:" -NoNewline
          Remove-Item -Path "$PROJECT_DIR\$_" -Recurse -Force
          if ( ! (Test-Path -Path "$PROJECT_DIR\$_") ) {
              Write-Result "Success" -ForegroundColor Green
          } else {
              Write-Result "Failed" -ForegroundColor Red
              exit 1
          }
      }
  }

  #-------------------------------------------------------------------------------
  # Installing dependencies
  #-------------------------------------------------------------------------------
  Write-Host "Installing dependencies: " -NoNewline
  Start-Process -FilePath $SCRIPTS_DIR\pip3.exe `
                -ArgumentList "install", "-r", "$SALT_DEPS" `
                -WorkingDirectory "$PROJECT_DIR" `
                -Wait -WindowStyle Hidden
  if ( Test-Path -Path "$SCRIPTS_DIR\distro.exe" ) {
      Write-Result "Success" -ForegroundColor Green
  } else {
      Write-Result "Failed" -ForegroundColor Red
      exit 1
  }
}

#-------------------------------------------------------------------------------
# Cleaning Up Installation
#-------------------------------------------------------------------------------

# Remove WMI Test Scripts
Write-Host "Removing wmitest scripts: " -NoNewline
Remove-Item -Path "$SCRIPTS_DIR\wmitest*" -Force | Out-Null
if ( ! (Test-Path -Path "$SCRIPTS_DIR\wmitest*") ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Complete PyWin32 Installation
#-------------------------------------------------------------------------------
# Part of the PyWin32 installation requires you to run a batch file that
# finalizes the installation. The following performs those actions:

# Move DLL's to Python Root and win32
# The dlls have to be in Python directory and the site-packages\win32 directory
# TODO: Change this to 310... maybe
$dlls = "pythoncom$($PY_MAJOR_VERSION)$($PY_MINOR_VERSION).dll",
        "pywintypes$($PY_MAJOR_VERSION)$($PY_MINOR_VERSION).dll"
$dlls | ForEach-Object {
    if ( -not ( Test-Path -Path "$SCRIPTS_DIR\$_" ) ) {
        Write-Host "Copying $_ to Scripts: " -NoNewline
        Copy-Item "$SITE_PKGS_DIR\pywin32_system32\$_" "$SCRIPTS_DIR" -Force | Out-Null
        if ( Test-Path -Path "$SCRIPTS_DIR\$_") {
            Write-Result "Success" -ForegroundColor Green
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
    if ( -not ( Test-Path -Path "$SITE_PKGS_DIR\win32\$_" ) ) {
        Write-Host "Moving $_ to win32: " -NoNewline
        Copy-Item "$SITE_PKGS_DIR\pywin32_system32\$_" "$SITE_PKGS_DIR\win32" -Force | Out-Null
        if ( Test-Path -Path "$SITE_PKGS_DIR\win32\$_" ) {
            Write-Result "Success" -ForegroundColor Green
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

if ( $PKG ) {
    # Remove pywin32_system32 directory since it is now empty
    if ( Test-Path -Path "$SITE_PKGS_DIR\pywin32_system32" ) {
        Write-Host "Removing pywin32_system32 directory: " -NoNewline
        Remove-Item -Path "$SITE_PKGS_DIR\pywin32_system32" -Recurse | Out-Null
        if ( ! (Test-Path -Path "$SITE_PKGS_DIR\pywin32_system32") ) {
            Write-Result "Success" -ForegroundColor Green
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

# Remove PyWin32 PostInstall & testall scripts
if ( Test-Path -Path "$SCRIPTS_DIR\pywin32_*" ) {
    Write-Host "Removing pywin32 post-install scripts: " -NoNewline
    Remove-Item -Path "$SCRIPTS_DIR\pywin32_*" -Force | Out-Null
    if ( ! (Test-Path -Path "$SCRIPTS_DIR\pywin32_*") ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

# Create gen_py directory
if ( ! (Test-Path -Path "$SITE_PKGS_DIR\win32com\gen_py" ) ) {
    Write-Host "Creating gen_py directory: " -NoNewline
    New-Item -Path "$SITE_PKGS_DIR\win32com\gen_py" -ItemType Directory -Force | Out-Null
    if ( Test-Path -Path "$SITE_PKGS_DIR\win32com\gen_py" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

if ( ! $SkipInstall ) {
  #-------------------------------------------------------------------------------
  # Installing Salt
  #-------------------------------------------------------------------------------
  Write-Host "Installing Salt: " -NoNewline
# We're setting RELENV_PIP_DIR so the binaries will be placed in the root
  if ( $SourceTarball ) {
      $InstallPath = $SourceTarball
  } else {
      $InstallPath = "."
  }
  try {
      $env:RELENV_PIP_DIR = "yes"
      Start-Process -FilePath $SCRIPTS_DIR\pip3.exe `
                -ArgumentList "install", $InstallPath `
                -WorkingDirectory "$PROJECT_DIR" `
                -Wait -WindowStyle Hidden
  } finally {
      Remove-Item env:\RELENV_PIP_DIR
  }
  if ( Test-Path -Path "$BUILD_DIR\salt-minion.exe" ) {
      Write-Result "Success" -ForegroundColor Green
  } else {
      Write-Result "Failed" -ForegroundColor Red
      exit 1
  }
}

if ( $PKG ) {
    # Remove fluff
    $remove = "doc",
              "readme",
              "salt-api",
              "salt-key",
              "salt-run",
              "salt-syndic",
              "salt-unity",
              "share",
              "spm",
              "wheel"
    $remove | ForEach-Object {
        if ( Test-Path -Path "$BUILD_DIR\$_*" ) {
            Write-Host "Removing $_`: " -NoNewline
            Remove-Item -Path "$BUILD_DIR\$_*" -Recurse
            if ( ! ( Test-Path -Path "$BUILD_DIR\$_*" ) ) {
                Write-Result "Success" -ForegroundColor Green
            } else {
                Write-Result "Failed" -ForegroundColor Red
                exit 1
            }
        }
    }
}
#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "Install Salt into Python Environment Complete" `
    -ForegroundColor Cyan
Write-Host $("=" * 80)
