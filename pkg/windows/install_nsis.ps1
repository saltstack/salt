<#
.SYNOPSIS
Script that installs NullSoft Installer

.DESCRIPTION
This script installs the NullSoft installer and all Plugins and Libraries
required to build the Salt installer

.EXAMPLE
install_nsis.ps1

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

$NSIS_DIR     = "${env:ProgramFiles(x86)}\NSIS"
$NSIS_PLUG_A  = "$NSIS_DIR\Plugins\x86-ansi"
$NSIS_PLUG_U  = "$NSIS_DIR\Plugins\x86-unicode"
$NSIS_LIB_DIR = "$NSIS_DIR\Include"
$DEPS_URL = "https://repo.saltproject.io/windows/dependencies"

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Install NullSoft Installer Software and Plugins" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# NSIS
#-------------------------------------------------------------------------------

Write-Host "Looking for NSIS: " -NoNewline
$check_file = "$NSIS_DIR\NSIS.exe"
if ( Test-Path -Path "$check_file" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Downloading NSIS: " -NoNewline
    $url = "$DEPS_URL/nsis-3.03-setup.exe"
    $file = "$env:TEMP\install_nsis.exe"
    Invoke-WebRequest -Uri $url -OutFile "$file"
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Installing NSIS: " -NoNewline
    Start-Process $file -ArgumentList "/S" -Wait -NoNewWindow
    if ( Test-Path -Path "$check_file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Cleaning up: " -NoNewline
    Remove-Item -Path $file -Force
    if ( ! (Test-Path -Path "$file") ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    }
}

#-------------------------------------------------------------------------------
# NSIS NxS Unzip Plugin
#-------------------------------------------------------------------------------

Write-Host "Looking for NSIS NxS Unzip (ansi) Plugin: " -NoNewline
$check_file = "$NSIS_PLUG_A\nsisunz.dll"
if ( Test-Path -Path $check_file ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Downloading NSIS NxS Unzip (ansi) Plugin: " -NoNewline
    $url = "$DEPS_URL/nsis-plugin-nsisunz.zip"
    $file = "$env:TEMP\nsizunz.zip"
    Invoke-WebRequest -Uri $url -OutFile "$file"
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Extracting NSIS NxS Unzip (ansi) Plugin: " -NoNewline
    Expand-Archive -Path "$file" -DestinationPath "$env:TEMP"
    if ( Test-Path -Path "$env:TEMP\nsisunz\Release\nsisunz.dll") {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Moving DLL to plugins directory: " -NoNewline
    Move-Item -Path "$env:TEMP\nsisunz\Release\nsisunz.dll" -Destination "$check_file" -Force
    if ( Test-Path -Path $check_file ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Cleaning up: " -NoNewline
    Remove-Item -Path $file -Force
    Remove-Item -Path "$env:TEMP\nsisunz" -Force -Recurse | Out-Null
    if ( Test-Path -Path "$file" ) {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    }
    if ( Test-Path -Path "$env:TEMP\nsisunz" ) {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

Write-Host "Looking for NSIS NxS Unzip (unicode) Plugin: " -NoNewline
$check_file = "$NSIS_PLUG_U\nsisunz.dll"
if ( Test-Path -Path $check_file ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Downloading NSIS NxS Unzip (unicode) Plugin: " -NoNewline
    $url = "$DEPS_URL/nsis-plugin-nsisunzu.zip"
    $file = "$env:TEMP\nsisunzu.zip"
    Invoke-WebRequest -Uri $url -OutFile "$file"
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Extracting NSIS NxS Unzip (unicode) Plugin: " -NoNewline
    Expand-Archive -Path "$file" -DestinationPath "$env:TEMP"
    if ( Test-Path -Path "$env:TEMP\NSISunzU\Plugin unicode\nsisunz.dll") {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Moving DLL to plugins directory: " -NoNewline
    Move-Item -Path "$env:TEMP\NSISunzU\Plugin unicode\nsisunz.dll" -Destination "$check_file" -Force
    if ( Test-Path -Path $check_file ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Cleaning up: " -NoNewline
    Remove-Item -Path $file -Force
    Remove-Item -Path "$env:TEMP\NSISunzU" -Force -Recurse | Out-Null
    if ( Test-Path -Path "$file" ) {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    }
    if ( Test-Path -Path "$env:TEMP\NSISunzU" ) {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# NSIS EnVar Plugin
#-------------------------------------------------------------------------------

Write-Host "Looking for NSIS EnVar Plugin: " -NoNewline
$check_file_a = "$NSIS_PLUG_A\EnVar.dll"
$check_file_u = "$NSIS_PLUG_U\EnVar.dll"
if ( (Test-Path -Path $check_file_a) -and (Test-Path -Path $check_file_u) ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Downloading NSIS EnVar Plugin: " -NoNewline
    $url = "$DEPS_URL/nsis-plugin-envar.zip"
    $file = "$env:TEMP\nsisenvar.zip"
    Invoke-WebRequest -Uri $url -OutFile "$file"
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Extracting NSIS EnVar Plugin: " -NoNewline
    Expand-Archive -Path "$file" -DestinationPath "$env:TEMP\nsisenvar\"
    if ( ! (Test-Path -Path "$env:TEMP\nsisenvar\Plugins\x86-ansi\EnVar.dll") ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
    if ( Test-Path -Path "$env:TEMP\nsisenvar\Plugins\x86-unicode\EnVar.dll" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Moving DLLs to plugins directory: " -NoNewline
    Move-Item -Path "$env:TEMP\nsisenvar\Plugins\x86-ansi\EnVar.dll" -Destination "$check_file_a" -Force
    Move-Item -Path "$env:TEMP\nsisenvar\Plugins\x86-unicode\EnVar.dll" -Destination "$check_file_u" -Force
    if ( ! (Test-Path -Path $check_file_a) ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
    if ( Test-Path -Path $check_file_u ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Cleaning up: " -NoNewline
    Remove-Item -Path $file -Force
    Remove-Item -Path "$env:TEMP\nsisenvar" -Force -Recurse | Out-Null
    if ( Test-Path -Path "$file" ) {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    }
    if ( Test-Path -Path "$env:TEMP\NSISunzU" ) {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# NSIS AccessControl Plugin
#-------------------------------------------------------------------------------

Write-Host "Looking for NSIS AccessControl Plugin: " -NoNewline
$check_file_a = "$NSIS_PLUG_A\AccessControl.dll"
$check_file_u = "$NSIS_PLUG_U\AccessControl.dll"
if ( (Test-Path -Path $check_file_a) -and (Test-Path -Path $check_file_u) ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Downloading NSIS AccessControl Plugin: " -NoNewline
    $url = "$DEPS_URL/nsis-plugin-accesscontrol.zip"
    $file = "$env:TEMP\nsisaccesscontrol.zip"
    Invoke-WebRequest -Uri $url -OutFile "$file"
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Extracting NSIS EnVar Plugin: " -NoNewline
    Expand-Archive -Path "$file" -DestinationPath "$env:TEMP\nsisaccesscontrol\"
    if ( ! (Test-Path -Path "$env:TEMP\nsisaccesscontrol\Plugins\i386-ansi\AccessControl.dll") ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
    if ( Test-Path -Path "$env:TEMP\nsisaccesscontrol\Plugins\i386-unicode\AccessControl.dll" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Moving DLLs to plugins directory: " -NoNewline
    Move-Item -Path "$env:TEMP\nsisaccesscontrol\Plugins\i386-ansi\AccessControl.dll" -Destination "$check_file_a" -Force
    Move-Item -Path "$env:TEMP\nsisaccesscontrol\Plugins\i386-unicode\AccessControl.dll" -Destination "$check_file_u" -Force
    if ( ! (Test-Path -Path $check_file_a) ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
    if ( Test-Path -Path $check_file_u ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Cleaning up: " -NoNewline
    Remove-Item -Path $file -Force
    Remove-Item -Path "$env:TEMP\nsisaccesscontrol" -Force -Recurse | Out-Null
    if ( Test-Path -Path "$file" ) {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    }
    if ( Test-Path -Path "$env:TEMP\nsisaccesscontrol" ) {
        # Not a hard fail
        Write-Result "Failed" -ForegroundColor Yellow
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# NSIS MoveFileFolder Library
#-------------------------------------------------------------------------------

Write-Host "Looking for NSIS MoveFileFolder Library: " -NoNewline
$check_file = "$NSIS_LIB_DIR\MoveFileFolder.nsh"
if ( Test-Path -Path $check_file ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Installing NSIS MoveFileFolder Library: " -NoNewline
    $url = "$DEPS_URL/nsis-MoveFileFolder.nsh"
    $file = "$check_file"
    Invoke-WebRequest -Uri $url -OutFile "$file"
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Script Finished
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Install NullSoft Installer Software and Plugins Completed" `
    -ForegroundColor Cyan
Write-Host $("=" * 80)
