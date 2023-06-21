<#
.SYNOPSIS
Script for setting up an additional salt-minion on a machine with Salt installed

.DESCRIPTION
This script configures an additional minion on a machine that already has a Salt
installation using one of the Salt packages. It sets up the directory structure
required by Salt. It also lays down a minion config to be used
by the Salt minion. Additionaly, this script can start the new minion in a
hidden window.

You can also remove the multiminion setup with this script.

This script does not need to be run with Administrator privileges

If a minion that was configured with this script is already running, the script
will exit.

The following example sets up a minion for the current logged in account. It
configures the minion to connect to the master at 192.168.0.10

.EXAMPLE
PS>multi-minion.ps1 -Master 192.168.0.10
PS>multi-minion.ps1 -m 192.168.0.10

The following example sets up a minion for the current logged in account. It
configures the minion to connect to the master at 192.168.0.10. It also prefixes
the minion id with `spongebob`

.EXAMPLE
PS>multi-minion.ps1 -Master 192.168.0.10 -Prefix spongebob
PS>multi-minion.ps1 -m 192.168.0.10 -p spongebob

The following example sets up a minion for the current logged in account. It
configures the minion to connect to the master at 192.168.0.10. It also starts
the minion in a hidden window:

.EXAMPLE
PS>multi-minion.ps1 -Master 192.168.0.10 -Start
PS>multi-minion.ps1 -m 192.168.0.10 -s

The following example removes a multiminion for the current running account:

.EXAMPLE
PS>multi-minion.ps1 -Delete
PS>multi-minion.ps1 -d

#>

[CmdletBinding()]
param(

    [Parameter(Mandatory=$false)]
    [Alias("m")]
    # The master to connect to. This can be an ip address or an fqdn. Default
    # is salt
    [String] $Master = "salt",

    [Parameter(Mandatory=$false)]
    [Alias("p")]
    # The prefix to the minion id to differentiate it from the installed system
    # minion. The default is $env:COMPUTERNAME. It might be helpful to use the
    # minion id of the system minion if you know it
    [String] $Prefix = "$env:COMPUTERNAME",

    [Parameter(Mandatory=$false)]
    [Alias("s")]
    # Start the minion in the background
    [Switch] $Start,

    [Parameter(Mandatory=$false)]
    [Alias("l")]
    [ValidateSet(
        "all",
        "garbage",
        "trace",
        "debug",
        "profile",
        "info",
        "warning",
        "error",
        "critical",
        "quiet"
    )]
    # Set the log level for log file. Default is `warning`
    [String] $LogLevel = "warning",

    [Parameter(Mandatory=$false)]
    [Alias("d")]
    # Remove the multi-minion in the current account. All other parameters are
    # ignored
    [Switch] $Remove
)

########################### Script Variables #############################
$user_name = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name.Split("\")[-1].ToLower()
$salt_bin = "$env:ProgramFiles\Salt Project\Salt\salt-minion.exe"
$root_dir = "$env:LocalAppData\Salt Project\Salt"
$cache_dir = "$root_dir\var\cache\salt\minion"
$minion_id = "$Prefix-$user_name"

########################### Script Functions #############################
function Test-FileLock {
    param (
        [parameter(Mandatory=$true)]
        # The path to the file to check
        [string]$Path
    )
    if ((Test-Path -Path $Path) -eq $false) {
        return $false
    }
    $oFile = New-Object System.IO.FileInfo $Path
    try {
        $oStream = $oFile.Open([System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        if ($oStream) {
            $oStream.Close()
        }
        return $false
    } catch {
        # file is locked by a process.
        return $true
    }
}

################################ Remove ##################################
if ( $Remove ) {
    Write-Host "######################################################################" -ForegroundColor Cyan
    Write-Host "Removing multi-minion"
    Write-Host "Root Dir: $root_dir"
    Write-Host "######################################################################" -ForegroundColor Cyan

    # Stop salt-minion service if running
    $processes = Get-WmiObject win32_process -filter "name like '%salt-minion%'" | Select-Object commandline,handle
    $processes | ForEach-Object {
        if ( $_.commandline -like "*$root_dir*" ) {
            Write-Host "Killing process: " -NoNewline
            $process = Get-Process -Id $_.handle
            $process.Kill()
            if ( $process.HasExited ) {
                Write-Host "Success" -ForegroundColor Green
            } else {
                Write-Host "Failed" -ForegroundColor Red
                exit 1
            }
        }
    }

    # Check for locked log file
    # The  log file will be locked until the running process releases it
    while (Test-FileLock -Path "$root_dir\var\log\salt\minion") {
        Start-Sleep -Seconds 1
    }

    # Remove Directory
    if ( Test-Path -Path $root_dir) {
        Write-Host "Removing Root Dir: " -NoNewline
        Remove-Item -Path $root_dir -Force -Recurse

        if ( !(Test-Path -Path $root_dir) ) {
            Write-Host "Success" -ForegroundColor Green
        } else {
            Write-Host "Failed" -ForegroundColor Red
            exit 1
        }
    }
    # Remind to delete keys from master
    Write-Host "######################################################################" -ForegroundColor Cyan
    Write-Host "Multi-Minion successfully removed"
    Write-Host ">>>>> Don't forget to remove keys from the master <<<<<"
    Write-Host "######################################################################" -ForegroundColor Cyan
    exit 0
}

################################ EXISTING CHECK ################################

# See there is already a running minion
$running = $false
$processes = Get-WmiObject win32_process -filter "name like '%salt-minion%'" | Select-Object commandline,handle
$processes | ForEach-Object {
    if ( $_.commandline -like "*$root_dir*" ) {
        $running = $true
    }
}
if ( $running ) {
    Write-Host "######################################################################" -ForegroundColor Cyan
    Write-Host "Multi-Minion"
    Write-Host "A minion is already running for this user"
    Write-Host "######################################################################" -ForegroundColor Cyan
    exit 0
}

################################### INSTALL ####################################

Write-Host "######################################################################" -ForegroundColor Cyan
Write-Host "Installing Multi-Minion"
Write-Host "Master:          $Master"
Write-Host "Minion ID:       $minion_id"
Write-Host "Root Directory:  $root_dir"
Write-Host "######################################################################" -ForegroundColor Cyan

# Create Root Directory Structure
if ( !( Test-Path -path "$root_dir" ) ) {
    Write-Host "Creating Root Dir: " -NoNewline
    New-Item -Path "$root_dir" -Type Directory | Out-Null
    if ( Test-Path -path "$root_dir" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Config dir
if ( !( Test-Path -path "$root_dir\conf" ) ) {
    Write-Host "Creating config dir: " -NoNewline
    New-Item -Path "$root_dir\conf" -Type Directory | Out-Null
    if ( Test-Path -path "$root_dir\conf" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Minion.d dir
if ( !( Test-Path -path "$root_dir\conf\minion.d" ) ) {
    Write-Host "Creating minion.d dir: " -NoNewline
    New-Item -Path "$root_dir\conf\minion.d" -Type Directory | Out-Null
    if ( Test-Path -path "$root_dir\conf\minion.d" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# PKI dir
if ( !( Test-Path -path "$root_dir\conf\pki" ) ) {
    Write-Host "Creating pki dir: " -NoNewline
    New-Item -Path "$root_dir\conf\pki" -Type Directory | Out-Null
    if ( Test-Path -path "$root_dir\conf\pki" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Log dir
if ( !( Test-Path -path "$root_dir\var\log\salt" ) ) {
    Write-Host "Creating log dir: " -NoNewline
    New-Item -Path "$root_dir\var\log\salt" -Type Directory | Out-Null
    if ( Test-Path -path "$root_dir\var\log\salt" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Run dir
if ( !( Test-Path -path "$root_dir\var\run" ) ) {
    Write-Host "Creating run dir: " -NoNewline
    New-Item -Path "$root_dir\var\run" -Type Directory | Out-Null
    if ( Test-Path -path "$root_dir\var\run" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Extmods grains dir
if ( !( Test-Path -path "$cache_dir\extmods\grains" ) ) {
    Write-Host "Creating extmods grains dir: " -NoNewline
    New-Item -Path "$cache_dir\extmods\grains" -Type Directory | Out-Null
    if ( Test-Path -path "$cache_dir\extmods\grains" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Proc dir
if ( !( Test-Path -path "$cache_dir\proc" ) ) {
    Write-Host "Creating proc dir: " -NoNewline
    New-Item -Path "$cache_dir\proc" -Type Directory | Out-Null
    if ( Test-Path -path "$cache_dir\proc" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Write minion config
Write-Host "Writing minion config: " -NoNewline
Set-Content -Force -Path "$root_dir\conf\minion" -Value "master: $Master"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "id: $minion_id"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "root_dir: $root_dir"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "log_file: $root_dir\var\log\salt\minion"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "log_level_logfile: $LogLevel"

Add-Content -Force -Path "$root_dir\conf\minion" -Value "utils_dirs:"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "  - $root_dir\var\cache\salt\minion\extmods\utils"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "winrepo_dir: $root_dir\srv\salt\win\repo"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "winrepo_dir_ng: $root_dir\srv\salt\win\repo-ng"

Add-Content -Force -Path "$root_dir\conf\minion" -Value "file_roots:"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "  base:"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "    - $root_dir\srv\salt"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "    - $root_dir\srv\spm\salt"

Add-Content -Force -Path "$root_dir\conf\minion" -Value "pillar_roots:"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "  base:"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "    - $root_dir\srv\pillar"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "    - $root_dir\srv\spm\pillar"

Add-Content -Force -Path "$root_dir\conf\minion" -Value "thorium_roots:"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "  base:"
Add-Content -Force -Path "$root_dir\conf\minion" -Value "    - $root_dir\srv\thorium"

if ( Test-Path -path "$root_dir\conf\minion" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

# Start the minion
if ( $Start ) {
    Write-Host "Starting minion process: " -NoNewline
    Start-Process -FilePath "`"$salt_bin`"" `
                  -ArgumentList "-c","`"$root_dir\conf`"" `
                  -WindowStyle Hidden
    # Verify running minion
    $running = $false
    $processes = Get-WmiObject win32_process -filter "name like '%salt-minion%'" | Select-Object commandline,handle
    $processes | ForEach-Object {
        if ( $_.commandline -like "*$root_dir*" ) {
            $running = $true
        }
    }
    if ( $running ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host "######################################################################" -ForegroundColor Cyan
Write-Host "Multi-Minion installed successfully"
if ( ! $Start ) {
    Write-Host ""
    Write-Host "To start the minion, run the following command:"
    Write-Host "salt-minion -c `"$root_dir\conf`""
    Write-Host ""
    Write-Host "To start the minion in the background, run the following command:"
    Write-Host "Start-Process -FilePath salt-minion.exe -ArgumentList `"-c`",'`"$root_dir\conf`"' -WindowStyle Hidden"
}
Write-Host "######################################################################" -ForegroundColor Cyan
