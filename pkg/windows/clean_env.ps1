<#
.SYNOPSIS
Script that cleans the build environment

.DESCRIPTION
This script uninstalls all versions of Python on the System. It also removes
Python from the system path. Additional, it removes the Python Launcher.

.EXAMPLE
clean_env.ps1

#>

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

Write-Host $("=" * 80)
Write-Host "Cleaning Build Environment" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Remove all Python 2 Installations
#-------------------------------------------------------------------------------
$packages = Get-Package | where { $_.Name -match "^Python 2.*$" }
$packages | ForEach-Object {
    $pkg_name = $_.Name
    Write-Host "Uninstalling $($pkg_name): " -NoNewline
    Start-Process -FilePath MsiExec.exe `
                  -ArgumentList "/X", "$( $_.FastPackageReference )", "/QN" `
                  -Wait -WindowStyle Hidden
    $test = Get-Package | where { $_.Name -eq $pkg_name }
    if ( $test.Count -eq 0 ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}
#-------------------------------------------------------------------------------
# Remove all Python 3 Installations
#-------------------------------------------------------------------------------
$packages = Get-Package | where {($_.Name -match "^Python 3.*$") -and ($_.ProviderName -eq "Programs") }
$packages | ForEach-Object {
    $pkg_name = $_.Name
    Write-Host "Uninstalling $($pkg_name): " -NoNewline
    $null, $uninstaller, $arguments = $_.Metadata["QuietUninstallString"] -Split('"')
    $arguments = $arguments.Trim().Split()
    Start-Process -FilePath $uninstaller `
                    -ArgumentList $arguments `
                    -Wait
    $test = Get-Package | where { $_.Name -eq $pkg_name }
    if ( $test.Count -eq 0 ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Remove Python Launcher
#-------------------------------------------------------------------------------
$packages = Get-Package | where { $_.Name -match "^Python Launcher$" }
$packages | ForEach-Object {
    $pkg_name = $_.Name
    Write-Host "Uninstalling $($pkg_name): " -NoNewline
    Start-Process -FilePath MsiExec.exe `
                  -ArgumentList "/X", "$( $_.FastPackageReference )", "/QN" `
                  -Wait -WindowStyle Hidden
    $test = Get-Package | where { $_.Name -eq $pkg_name }
    if ( $test.Count -eq 0 ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Remove all Python Directories
#-------------------------------------------------------------------------------
$paths = "$env:SystemDrive\Python27",
         "$env:SystemDrive\Python36",
         "$env:SystemDrive\Python37",
         "$env:SystemDrive\Python38",
         "$env:SystemDrive\Python39",
         "$env:SystemDrive\Python310"
$paths | ForEach-Object {
    if ( Test-Path -Path $_ ) {
        Write-Host "Removing $($_): " -NoNewline
        Remove-Item -Path $_ -Recurse -Force
        if ( ! (Test-Path -Path "$_") ) {
            Write-Host "Success" -ForegroundColor Green
        } else {
            Write-Host "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

#-------------------------------------------------------------------------------
# Clean Path Environment Variable
#-------------------------------------------------------------------------------
$system_paths = [Environment]::GetEnvironmentVariable("PATH", "Machine").Split(";")
$new_path = [System.Collections.ArrayList]::New()

$found_in_path = $false
$paths | ForEach-Object {
    if ( $_ -in $system_paths ) {
        $found_in_path = $true
    }
}

if ( $found_in_path ) {
    Write-Host "Removing Python from PATH: " -NoNewline
    $system_paths | ForEach-Object {
        $found = $false
        if ($_ -match "^[A-Z]:\\Python\d{2,3}.*") {
            $found = $true
        }
        if (!$found) {
            $new_path.Add($_) | Out-Null
        }
    }

    if ( ! [String]::IsNullOrEmpty($new_path) ) {
        [Environment]::SetEnvironmentVariable("PATH", $new_path -join ";", [EnvironmentVariableTarget]::Machine)
        $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine")
    }

    $found_in_path = $false
    $paths | ForEach-Object {
        if ( $_ -in $env:PATH ) {
            $found_in_path = $true
        }
    }
    if ( ! $found_in_path ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}


#-------------------------------------------------------------------------------
# Remove Python Launcher Registry Keys
#-------------------------------------------------------------------------------
if ( Test-Path -Path HKLM:\SOFTWARE\Python ) {
    Write-Host "Removing Python Launcher Registry Keys: " -NoNewline
    Remove-Item -Path HKLM:\SOFTWARE\Python -Recurse -Force
    if ( ! (Test-Path -Path HKLM:\SOFTWARE\Python) ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Done
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "Cleaning Build Environment Complete" -ForegroundColor Cyan
Write-Host $("=" * 80)
