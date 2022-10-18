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
    [ValidateSet("x86", "x64")]
    [Alias("a")]
    # The System Architecture to build. "x86" will build a 32-bit installer.
    # "x64" will build a 64-bit installer. Default is: x64
    $Architecture = "x64"
)

# Script Preferences
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Import Modules
#-------------------------------------------------------------------------------
$SCRIPT_DIR = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
Import-Module $SCRIPT_DIR\Modules\uac-module.psm1

#-------------------------------------------------------------------------------
# Check for Elevated Privileges
#-------------------------------------------------------------------------------
If (!(Get-IsAdministrator)) {
    If (Get-IsUacEnabled) {
        # We are not running "as Administrator" - so relaunch as administrator
        # Create a new process object that starts PowerShell
        $newProcess = new-object System.Diagnostics.ProcessStartInfo "PowerShell";

        # Specify the current script path and name as a parameter
        $newProcess.Arguments = $myInvocation.MyCommand.Definition

        # Specify the current working directory
        $newProcess.WorkingDirectory = "$SCRIPT_DIR"

        # Indicate that the process should be elevated
        $newProcess.Verb = "runas";

        # Start the new process
        [System.Diagnostics.Process]::Start($newProcess);

        # Exit from the current, unelevated, process
        Exit
    } Else {
        Throw "You must be administrator to run this script"
    }
}

#-------------------------------------------------------------------------------
# Define Variables
#-------------------------------------------------------------------------------

# Python Variables
$PY_VERSION     = "3.8"
$PYTHON_DIR     = "C:\Python$($PY_VERSION -replace "\.")"
$PYTHON_BIN     = "$PYTHON_DIR\python.exe"
$SCRIPTS_DIR    = "$PYTHON_DIR\Scripts"
$SITE_PKGS_DIR  = "$PYTHON_DIR\Lib\site-packages"

# Script Variables
$PROJECT_DIR     = $(git rev-parse --show-toplevel)
$SALT_REPO_URL   = "https://github.com/saltstack/salt"
$SALT_SRC_DIR    = "$( (Get-Item $PROJECT_DIR).Parent.FullName )\salt"
$SALT_DEPS       = "$SALT_SRC_DIR\requirements\static\pkg\py$PY_VERSION\windows.txt"
if ( $Architecture -eq "x64" ) {
    $SALT_DEP_URL   = "https://repo.saltproject.io/windows/dependencies/64"
} else {
    $SALT_DEP_URL   = "https://repo.saltproject.io/windows/dependencies/32"
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Install Salt into Python Environment" -ForegroundColor Cyan
Write-Host "- Architecture: $Architecture"
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Installing Salt
#-------------------------------------------------------------------------------
# We don't want to use an existing salt installation because we don't know what
# it is
Write-Host "Checking for existing Salt installation: " -NoNewline
if ( ! (Test-Path -Path "$SCRIPTS_DIR\salt-minion.exe") ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Cleaning Salt Build Environment: " -NoNewline
$remove = "build", "dist"
$remove | ForEach-Object {
    if ( Test-Path -Path "$SALT_SRC_DIR\$_" ) {
        Remove-Item -Path "$SALT_SRC_DIR\$_" -Recurse -Force
        if ( Test-Path -Path "$SALT_SRC_DIR\$_" ) {
            Write-Host "Failed" -ForegroundColor Red
            Write-Host "Failed to remove $_"
            exit 1
        }
    }
}
Write-Host "Success" -ForegroundColor Green

Write-Host "Installing Salt: " -NoNewline
Start-Process -FilePath $SCRIPTS_DIR\pip.exe `
              -ArgumentList "install", "." `
              -WorkingDirectory "$SALT_SRC_DIR" `
              -Wait -WindowStyle Hidden
if ( Test-Path -Path "$SCRIPTS_DIR\salt-minion.exe" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Copying Scripts: " -NoNewline
$salt_binaries = Get-ChildItem -Path $SCRIPTS_DIR -Filter "salt*.exe"
$salt_binaries | ForEach-Object {
    Copy-Item -Path "$SALT_SRC_DIR\scripts\$($_.BaseName)" `
              -Destination "$SCRIPTS_DIR" -Force
}
$salt_files = Get-ChildItem -Path $SCRIPTS_DIR -Filter "salt*"
if ( $salt_files.Count -eq ($salt_binaries.Count * 2) ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
}

#-------------------------------------------------------------------------------
# Installing Libsodium DLL
#-------------------------------------------------------------------------------
Write-Host "Installing Libsodium DLL: " -NoNewline
$libsodium_url = "$SALT_DEP_URL/libsodium/1.0.18/libsodium.dll"
Invoke-WebRequest -Uri $libsodium_url -OutFile "$PYTHON_DIR\libsodium.dll"
if ( Test-Path -Path "$PYTHON_DIR\libsodium.dll" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Cleaning Up Installation
#-------------------------------------------------------------------------------

# Remove doc
if ( Test-Path -Path "$PYTHON_DIR\doc" ) {
    Write-Host "Removing doc directory: " -NoNewline
    Remove-Item "$PYTHON_DIR\doc" -Recurse -Force
    if ( ! (Test-Path -Path "$PYTHON_DIR\doc") ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Remove share
if ( Test-Path -Path "$PYTHON_DIR\share" ) {
    Write-Host "Removing share directory: " -NoNewline
    Remove-Item "$PYTHON_DIR\share" -Recurse -Force
    if ( ! (Test-Path -Path "$PYTHON_DIR\share") ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Remove WMI Test Scripts
Write-Host "Removing wmitest scripts: " -NoNewline
Remove-Item -Path "$SCRIPTS_DIR\wmitest*" -Force | Out-Null
if ( ! (Test-Path -Path "$SCRIPTS_DIR\wmitest*") ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

# Remove Non-Minion Components
# TODO: These should probably be removed from Setup.py so they
# TODO: are not created in the first place
Write-Host "Removing Non-Minion Components: " -NoNewline
$remove = "salt-key",
          "salt-run",
          "salt-syndic",
          "salt-unity"
$remove | ForEach-Object {
    Remove-Item -Path "$SCRIPTS_DIR\$_*" -Recurse
    if ( Test-Path -Path "$SCRIPTS_DIR\$_*" ) {
        Write-Host "Failed" -ForegroundColor Red
        Write-Host "Failed to remove: $SCRIPTS_DIR\$_"
        exit 1
    }
}
Write-Host "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Cleaning PyWin32 Installation
#-------------------------------------------------------------------------------

# Move DLL's to Python Root
# The dlls have to be in Python directory and the site-packages\win32 directory
Write-Host "Placing PyWin32 DLLs: " -NoNewline
Copy-Item "$SITE_PKGS_DIR\pywin32_system32\*.dll" "$PYTHON_DIR" -Force | Out-Null
Move-Item "$SITE_PKGS_DIR\pywin32_system32\*.dll" "$SITE_PKGS_DIR\win32" -Force | Out-Null
if ( ! ((Test-Path -Path "$PYTHON_DIR\pythoncom38.dll") -and (Test-Path -Path "$PYTHON_DIR\pythoncom38.dll")) ) {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}
if ( (Test-Path -Path "$SITE_PKGS_DIR\win32\pythoncom38.dll") -and (Test-Path -Path "$SITE_PKGS_DIR\win32\pythoncom38.dll") ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

# Create gen_py directory
Write-Host "Creating gen_py directory: " -NoNewline
New-Item -Path "$SITE_PKGS_DIR\win32com\gen_py" -ItemType Directory -Force | Out-Null
if ( Test-Path -Path "$SITE_PKGS_DIR\win32com\gen_py" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

# Remove pywin32_system32 directory
Write-Host "Removing pywin32_system32 directory: " -NoNewline
Remove-Item -Path "$SITE_PKGS_DIR\pywin32_system32" | Out-Null
if ( ! (Test-Path -Path "$SITE_PKGS_DIR\pywin32_system32") ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

# Remove PyWin32 PostInstall & testall scripts
Write-Host "Removing pywin32 scripts: " -NoNewline
Remove-Item -Path "$SCRIPTS_DIR\pywin32_*" -Force | Out-Null
if ( ! (Test-Path -Path "$SCRIPTS_DIR\pywin32_*") ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "Install Salt into Python Environment Complete" `
    -ForegroundColor Cyan
Write-Host $("=" * 80)
