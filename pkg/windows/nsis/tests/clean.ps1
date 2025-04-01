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
# Script Variables
#-------------------------------------------------------------------------------

$SCRIPT_DIR = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$PROJECT_DIR   = $(git rev-parse --show-toplevel)
$WINDOWS_DIR   = "$PROJECT_DIR\pkg\windows"
$BUILDENV_DIR  = "$WINDOWS_DIR\buildenv"

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
# Remove buildenv directory
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$BUILDENV_DIR" ) {
    Write-Host "Removing buildenv directory: " -NoNewline
    Remove-Item -Path "$BUILDENV_DIR" -Recurse -Force
    if ( Test-Path -Path "$BUILDENV_DIR" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Make sure processes are not running
#-------------------------------------------------------------------------------
$processes = "test-setup",
             "Un",
             "Un_A",
             "Un_B",
             "Un_C",
             "Un_D",
             "Un_E",
             "Un_F",
             "Un_G"
$processes | ForEach-Object {
    $proc = Get-Process -Name $_ -ErrorAction SilentlyContinue
    if ( ($null -ne $proc) ) {
        Write-Host "Killing $($_): " -NoNewline
        $proc = Get-WmiObject -Class Win32_Process -Filter "Name='$_.exe'"
        $proc.Terminate() *> $null
        Start-Sleep -Seconds 5
        $proc = Get-Process -Name $_ -ErrorAction SilentlyContinue
        if ( ($null -eq $proc) ) {
            Write-Result "Success" -ForegroundColor Green
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
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
# Remove custom_conf
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$SCRIPT_DIR\custom_conf" ) {
    Write-Host "Removing custom_conf: " -NoNewline
    Remove-Item -Path "$SCRIPT_DIR\custom_conf" -Recurse -Force
    if ( Test-Path -Path "$SCRIPT_DIR\custom_conf" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove the salt-minion service
#-------------------------------------------------------------------------------
if ( $(Get-Service -Name salt-minion -ErrorAction SilentlyContinue).Name ) {
    Write-Host "Removing salt-minion service" -NoNewline
    Stop-Service -Name salt-minion
    $service = Get-WmiObject -Class Win32_Service -Filter "Name='salt-minion'"
    $service.delete() *> $null
    if ( $(Get-Service -Name salt-minion -ErrorAction SilentlyContinue).Name ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove Salt Project directory from Program Files
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$env:ProgramFiles\Salt Project" ) {
    Write-Host "Removing Salt Project from Program Files: " -NoNewline
    Remove-Item -Path "$env:ProgramFiles\Salt Project" -Recurse -Force
    if ( Test-Path -Path "$env:ProgramFiles\Salt Project" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove Salt Project directory from ProgramData
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$env:ProgramData\Salt Project" ) {
    Write-Host "Removing Salt Project from ProgramData: " -NoNewline
    Remove-Item -Path "$env:ProgramData\Salt Project" -Recurse -Force
    if ( Test-Path -Path "$env:ProgramData\Salt Project" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove Salt Project from Registry
#-------------------------------------------------------------------------------
if ( Test-Path -Path "HKLM:SOFTWARE\Salt Project" ) {
    Write-Host "Removing Salt Project from Software: " -NoNewline
    Remove-Item -Path "HKLM:SOFTWARE\Salt Project" -Recurse -Force
    if ( Test-Path -Path "HKLM:SOFTWARE\Salt Project" ) {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Result "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Remove Salt Minion directory from Registry
#-------------------------------------------------------------------------------
if ( Test-Path -Path "HKLM:SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Salt Minion" ) {
    Write-Host "Removing Salt Minion from the Uninstall: " -NoNewline
    Remove-Item -Path "HKLM:SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Salt Minion" -Recurse -Force
    if ( Test-Path -Path "HKLM:SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Salt Minion" ) {
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
