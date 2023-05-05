<#
.SYNOPSIS
Script for setting up an additional salt-minion on a machine with Salt installed

.DESCRIPTION
This script will install an additional minion on a machine that already has a
Salt installtion using one of the Salt packages. It will set up the directory
structure required by Salt. It will also lay down a minion config to be used
by the Salt minion. Additionaly, this script will install and start a Salt
minion service that uses the root_dir and minion config. You can also pass the
name of a service account to be used by the service.

You can also remove the multiminion setup with this script.

This script should be run with Administrator privileges

The following example will install a service named `salt-minion-mm10` that
starts with the LOCALSYSTEM account. It is the `-s` parameter that creates the
service:

.EXAMPLE
PS>multi-minion.ps1 -Name mm10 -s

The following example will install a service that starts with a user named
mmuser:

.EXAMPLE
PS>multi-minion.ps1 -Name mm10 -s -m 192.168.0.10 -u mmuser -p secretword

The following example will set up config for minion that can be run in the
background under a user account. Notice the command does not have the `-s`
parameter:

.EXAMPLE
PS>multi-minion.ps1 -Name mm10 -m 192.168.0.10

The following example will remove a multiminion that has been installed with
this script:

.EXAMPLE
PS>multi-minion.ps1 -Name mm10 -d

#>

[CmdletBinding()]
param(

    [Parameter(Mandatory=$true)]
    [Alias("n")]
    # The name used to create the service and root_dir. This is the only
    # required parameter
    [String] $Name,

    [Parameter(Mandatory=$false)]
    [Alias("m")]
    # The master to connect to. This can be an ip address or an fqdn. Default
    # is salt
    [String] $Master = "salt",

    [Parameter(Mandatory=$false)]
    [Alias("r")]
    # The root dir to place the minion config and directory structure. The
    # default is %PROGRAMDATA%\Salt Project\Salt-$Name
    [String] $RootDir = "$env:ProgramData\Salt Project\Salt-$Name",

    [Parameter(Mandatory=$false)]
    [Alias("u")]
    # User account to run the service under. The user account must be present on
    # the system. The default is to use the LOCALSYSTEM account
    [String] $User,

    [Parameter(Mandatory=$false)]
    [Alias("p")]
    # The password to the user account. Required if User is passed. We should
    # probably figure out how to make this more secure
    [String] $Password,

    [Parameter(Mandatory=$false)]
    [Alias("s")]
    # Set this switch to install the service. Default is to not install the
    # service
    [Switch] $Service,

    [Parameter(Mandatory=$false)]
    [Alias("d")]
    # Remove the specified multi-minion. All other parameters are ignored
    [Switch] $Remove
)

########################### Script Variables #############################
$ssm_bin = "$env:ProgramFiles\Salt Project\Salt\ssm.exe"
$salt_bin = "$env:ProgramFiles\Salt Project\Salt\salt-minion.exe"
$service_name = "salt-minion-$($Name.ToLower())"
$default_root_dir = Resolve-Path -Path "$env:ProgramData\Salt Project\Salt"
$cache_dir = "$RootDir\var\cache\salt\minion"

################################ Remove ##################################
if ( $Remove ) {
    Write-Host "######################################################################" -ForegroundColor Cyan
    Write-Host "Removing multi-minion"
    Write-Host "Name: $Name"
    Write-Host "Service Name: $service_name"
    Write-Host "Root Dir: $RootDir"
    Write-Host "######################################################################" -ForegroundColor Cyan

    # Stop Service
    $service_object = Get-Service -Name $service_name -ErrorAction SilentlyContinue
    if ( $service_object -and ($service_object.Status -ne "Stopped") ) {
        Write-Host "Stopping service: " -NoNewline
        Stop-Service -Name $service_name *> $null
        $service_object.Refresh()
        if ( $service_object.Status -eq "Stopped" ) {
            Write-Host "Success" -ForegroundColor Green
        } else {
            Write-Host "Failed" -ForegroundColor Red
            exit 1
        }
    }

    # Remove Service
    $service_object = Get-Service -Name $service_name -ErrorAction SilentlyContinue
    if ( $service_object ) {
        Write-Host "Removing service: " -NoNewline
        & $ssm_bin remove $service_name confirm *> $null
            $service_object = Get-Service -Name $service_name -ErrorAction SilentlyContinue
        if ( !$service_object ) {
            Write-Host "Success" -ForegroundColor Green
        } else {
            Write-Host "Failed" -ForegroundColor Red
            exit 1
        }
    }

    # Remove Directory
    if ( Test-Path -Path $RootDir ) {
        Write-Host "Removing RootDir: " -NoNewline
        Remove-Item -Path $RootDir -Force -Recurse

        if ( !(Test-Path -Path $RootDir) ) {
            Write-Host "Success" -ForegroundColor Green
        } else {
            Write-Host "Failed" -ForegroundColor Red
            exit 1
        }
    }
    # Remind to delete keys from master
    Write-Host "######################################################################" -ForegroundColor Cyan
    Write-Host "Multi-Minion installed successfully"
    Write-Host ">>>>> Don't forget to remove keys from the master <<<<<"
    Write-Host "######################################################################" -ForegroundColor Cyan
    exit 0
}

################################ Install #################################
# We don't want to share config with the current running minion
if ( $RootDir.Trim("\") -eq $default_root_dir ) {
    Write-Host "WARNING: RootDir can't be default Salt rootdir" -ForegroundColor Red
    exit 1
}

# Make sure password is set if user is passed
if ( $User -and !$Password ) {
    Write-Host "WARNING: You must pass a password when defining a user account" -ForegroundColor Red
    exit 1
}

Write-Host "######################################################################" -ForegroundColor Cyan
Write-Host "Installing multi-minion"
Write-Host "Name: $Name"
Write-Host "Master: $Master"
Write-Host "Root Directory: $RootDir"
Write-Host "Create Service: $Service"
if ( $Service ) {
    Write-Host "Service Account: $User"
    Write-Host "Password: **********"
    Write-Host "Service Name: $service_name"
}
Write-Host "######################################################################" -ForegroundColor Cyan

# Create file_roots Directory Structure
if ( !( Test-Path -path "$RootDir" ) ) {
    Write-Host "Creating RootDir: " -NoNewline
    New-Item -Path "$RootDir" -Type Directory | Out-Null
    if ( Test-Path -path "$RootDir" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Set permissions
if ( $User ) {
    Write-Host "Setting Permissions: " -NoNewline
    $acl = Get-Acl -Path "$RootDir"
    $access_rule = New-Object System.Security.AccessControl.FileSystemAccessRule($User, "Modify", "Allow")
    $acl.AddAccessRule($access_rule)
    Set-Acl -Path "$RootDir" -AclObject $acl

    $found = $false
    $acl = Get-Acl -Path "$RootDir"
    $acl.Access | ForEach-Object {
        if ( $_.IdentityReference.Value.Contains($User) ) {
            $found = $true
        }
    }
    if ( $found ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

# Child directories will inherit permissions from the parent
if ( !( Test-Path -path "$RootDir\conf" ) ) {
    Write-Host "Creating config dir: " -NoNewline
    New-Item -Path "$RootDir\conf" -Type Directory | Out-Null
    if ( Test-Path -path "$RootDir\conf" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}
if ( !( Test-Path -path "$RootDir\conf\minion.d" ) ) {
    Write-Host "Creating minion.d dir: " -NoNewline
    New-Item -Path "$RootDir\conf\minion.d" -Type Directory | Out-Null
    if ( Test-Path -path "$RootDir\conf\minion.d" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}
if ( !( Test-Path -path "$RootDir\conf\pki" ) ) {
    Write-Host "Creating pki dir: " -NoNewline
    New-Item -Path "$RootDir\conf\pki" -Type Directory | Out-Null
    if ( Test-Path -path "$RootDir\conf\pki" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}
if ( !( Test-Path -path "$RootDir\var\log\salt" ) ) {
    Write-Host "Creating log dir: " -NoNewline
    New-Item -Path "$RootDir\var\log\salt" -Type Directory | Out-Null
    if ( Test-Path -path "$RootDir\var\log\salt" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}
if ( !( Test-Path -path "$RootDir\var\run" ) ) {
    Write-Host "Creating run dir: " -NoNewline
    New-Item -Path "$RootDir\var\run" -Type Directory | Out-Null
    if ( Test-Path -path "$RootDir\var\run" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}
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
Add-Content -Force -Path "$RootDir\conf\minion" -Value "master: $Master"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "id: $Name"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "root_dir: $RootDir"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "log_file: $RootDir\var\log\salt\minion"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "utils_dirs: $RootDir\var\cache\salt\minion\extmods\utils"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "winrepo_dir: $RootDir\srv\salt\win\repo"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "winrepo_dir_ng: $RootDir\srv\salt\win\repo-ng"

Add-Content -Force -Path "$RootDir\conf\minion" -Value "file_roots:"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "  base:"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "    - $RootDir\srv\salt"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "    - $RootDir\srv\spm\salt"

Add-Content -Force -Path "$RootDir\conf\minion" -Value "pillar_roots:"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "  base:"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "    - $RootDir\srv\pillar"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "    - $RootDir\srv\spm\pillar"

Add-Content -Force -Path "$RootDir\conf\minion" -Value "thorium_roots:"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "  base:"
Add-Content -Force -Path "$RootDir\conf\minion" -Value "    - $RootDir\srv\thorium"

if ( Test-Path -path "$RootDir\conf\minion" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

if ( $Service ) {
    # Register salt-minion service using SSM
    Write-Host "Registering service $service_name`: " -NoNewline
    & $ssm_bin install $service_name "$salt_bin" "-c """"$RootDir\conf"""" -l quiet" *> $null
    & $ssm_bin set $service_name Description "Salt Minion $Name" *> $null
    & $ssm_bin set $service_name Start SERVICE_AUTO_START *> $null
    & $ssm_bin set $service_name AppStopMethodConsole 24000 *> $null
    & $ssm_bin set $service_name AppStopMethodWindow 2000 *> $null
    & $ssm_bin set $service_name AppRestartDelay 60000 *> $null
    if ( $User -and $Password ) {
        & $ssm_bin set $service_name ObjectName ".\$User" "$Password" *> $null
    }

    $service_object = Get-Service -Name $service_name -ErrorAction SilentlyContinue
    if ( $service_object ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Starting service: " -NoNewline
    Start-Service -Name $service_name
    $service_object.Refresh()
    if ( $service_object.Status -eq "Running" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host "######################################################################" -ForegroundColor Cyan
Write-Host "Multi-Minion installed successfully"
Write-Host "Root Directory: $RootDir"
if ( $Service ) {
    Write-Host "Service Name: $service_name"
} else {
    Write-Host "To start the minion, run the following command:"
    Write-Host "salt-minion -c `"$RootDir\conf`""
}
Write-Host "######################################################################" -ForegroundColor Cyan
