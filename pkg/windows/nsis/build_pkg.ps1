<#
.SYNOPSIS
Script that builds a NullSoft Installer package for Salt

.DESCRIPTION
This script takes the contents of the Python Directory that has Salt installed
and creates a NullSoft Installer based on that directory.

.EXAMPLE
build_pkg.ps1 -Version 3005

#>

param(
    [Parameter(Mandatory=$false)]
    [Alias("v")]
    # The version of Salt to be built. If this is not passed, the script will
    # attempt to get it from the git describe command on the Salt source
    # repo
    [String] $Version,

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

$PROJECT_DIR    = $(git rev-parse --show-toplevel)
$SCRIPT_DIR     = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$BUILD_DIR      = "$PROJECT_DIR\pkg\windows\build"
$BUILDENV_DIR   = "$PROJECT_DIR\pkg\windows\buildenv"
$INSTALLER_DIR  = "$SCRIPT_DIR\installer"
$SCRIPTS_DIR    = "$BUILDENV_DIR\Scripts"
$SITE_PKGS_DIR  = "$BUILDENV_DIR\Lib\site-packages"
$BUILD_SALT_DIR = "$SITE_PKGS_DIR\salt"
$PYTHON_BIN     = "$SCRIPTS_DIR\python.exe"
$PY_VERSION     = [Version]((Get-Command $PYTHON_BIN).FileVersionInfo.ProductVersion)
$PY_VERSION     = "$($PY_VERSION.Major).$($PY_VERSION.Minor)"
$NSIS_BIN       = "$( ${env:ProgramFiles(x86)} )\NSIS\makensis.exe"
$ARCH           = $(. $PYTHON_BIN -c "import platform; print(platform.architecture()[0])")

if ( $ARCH -eq "64bit" ) {
    $ARCH = "AMD64"
} else {
    $ARCH = "x86"
}

#-------------------------------------------------------------------------------
# Verify Salt and Version
#-------------------------------------------------------------------------------

if ( [String]::IsNullOrEmpty($Version) ) {
    $Version = $( git describe ).Trim("v")
    if ( [String]::IsNullOrEmpty($Version) ) {
        Write-Host "Failed to get version from $PROJECT_DIR"
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Build NullSoft Installer for Salt" -ForegroundColor Cyan
Write-Host "- Architecture: $ARCH"
Write-Host "- Salt Version: $Version"
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
if ( Test-Path -Path "$BUILDENV_DIR\salt-minion.exe" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Verifying NSIS Installation: " -NoNewline
if ( Test-Path -Path "$NSIS_BIN" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Copy the icon file to the build_env directory
#-------------------------------------------------------------------------------

Write-Host "Copying icon file to build env: " -NoNewline
Copy-Item "$INSTALLER_DIR\salt.ico" "$BUILDENV_DIR" | Out-Null
if ( Test-Path -Path "$INSTALLER_DIR\salt.ico" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    Write-Host "Failed to find salt.ico in build_env directory"
    exit 1
}

#-------------------------------------------------------------------------------
# Remove Non-Windows Execution Modules
#-------------------------------------------------------------------------------
Write-Host "Removing Non-Windows Execution Modules: " -NoNewline
$modules = "acme",
           "aix",
           "alternatives",
           "apcups",
           "apf",
           "apt",
           "arista",
           "at",
           "bcache",
           "blockdev",
           "bluez",
           "bridge",
           "bsd",
           "btrfs",
           "ceph",
           "container_resource",
           "cron",
           "csf",
           "daemontools",
           "deb*",
           "devmap",
           "dpkg",
           "ebuild",
           "eix",
           "eselect",
           "ethtool",
           "extfs",
           "firewalld",
           "freebsd",
           "genesis",
           "gentoo",
           "glusterfs",
           "gnomedesktop",
           "groupadd",
           "grub_legacy",
           "guestfs",
           "htpasswd",
           "ilo",
           "img",
           "incron",
           "inspector",
           "ipset",
           "iptables",
           "iwtools",
           "k8s",
           "kapacitor",
           "keyboard",
           "keystone",
           "kmod",
           "layman",
           "linux",
           "localemod",
           "locate",
           "logadm",
           "logrotate",
           "lvs",
           "lxc",
           "mac",
           "makeconf",
           "mdadm",
           "mdata",
           "monit",
           "moosefs",
           "mount",
           "napalm",
           "netbsd",
           "netscaler",
           "neutron",
           "nfs3",
           "nftables",
           "nova",
           "nspawn",
           "openbsd",
           "openstack",
           "openvswitch",
           "opkg",
           "pacman",
           "parallels",
           "parted",
           "pcs",
           "pkgin",
           "pkgng",
           "pkgutil",
           "portage_config",
           "postfix",
           "poudriere",
           "powerpath",
           "pw_",
           "qemu_",
           "quota",
           "redismod",
           "restartcheck",
           "rh_",
           "riak",
           "rpm",
           "runit",
           "s6",
           "scsi",
           "sensors",
           "service",
           "shadow",
           "smartos",
           "smf",
           "snapper",
           "solaris",
           "solr",
           "ssh_",
           "supervisord",
           "sysbench",
           "sysfs",
           "sysrc",
           "system",
           "test_virtual",
           "timezone",
           "trafficserver",
           "tuned",
           "udev",
           "upstart",
           "useradd",
           "uswgi",
           "varnish",
           "vbox",
           "virt",
           "xapi",
           "xbpspkg",
           "xfs",
           "yum*",
           "zfs",
           "znc",
           "zpool",
           "zypper"
$modules | ForEach-Object {
    Remove-Item -Path "$BUILD_SALT_DIR\modules\$_*" -Recurse
    if ( Test-Path -Path "$BUILD_SALT_DIR\modules\$_*" ) {
        Write-Result "Failed" -ForegroundColor Red
        Write-Host "Failed to remove: $BUILD_SALT_DIR\modules\$_"
        exit 1
    }
}
Write-Result "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Remove Non-Windows State Modules
#-------------------------------------------------------------------------------
Write-Host "Removing Non-Windows State Modules: " -NoNewline
$states = "acme",
          "alternatives",
          "apt",
          "at",
          "blockdev",
          "ceph",
          "cron",
          "csf",
          "deb",
          "eselect",
          "ethtool",
          "firewalld",
          "glusterfs",
          "gnome",
          "htpasswd",
          "incron",
          "ipset",
          "iptables",
          "k8s",
          "kapacitor",
          "keyboard",
          "keystone",
          "kmod",
          "layman",
          "linux",
          "lxc",
          "mac",
          "makeconf",
          "mdadm",
          "monit",
          "mount",
          "nftables",
          "pcs",
          "pkgng",
          "portage",
          "powerpath",
          "quota",
          "redismod",
          "smartos",
          "snapper",
          "ssh",
          "supervisord",
          "sysrc",
          "trafficserver",
          "tuned",
          "vbox",
          "virt.py",
          "zfs",
          "zpool"
$states | ForEach-Object {
    Remove-Item -Path "$BUILD_SALT_DIR\states\$_*" -Recurse
    if ( Test-Path -Path "$BUILD_SALT_DIR\states\$_*" ) {
        Write-Result "Failed" -ForegroundColor Red
        Write-Host "Failed to remove: $BUILD_SALT_DIR\states\$_"
        exit 1
    }
}
Write-Result "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Remove compiled files
#-------------------------------------------------------------------------------
# We have to do this again because we use the Relenv Python to get the build
# architecture. This recreates some of the pycache files that were removed
# in the prep_salt script
Write-Host "Removing __pycache__ directories: " -NoNewline
$found = Get-ChildItem -Path "$BUILDENV_DIR" -Filter "__pycache__" -Recurse
$found | ForEach-Object {
    Remove-Item -Path "$($_.FullName)" -Recurse -Force
    if ( Test-Path -Path "$($_.FullName)" ) {
        Write-Result "Failed" -ForegroundColor Red
        Write-Host "Failed to remove: $($_.FullName)"
        exit 1
    }
}
Write-Result "Success" -ForegroundColor Green

# If we try to remove *.pyc with the same Get-ChildItem that we used to remove
# __pycache__ directories, it won't be able to find them because they are no
# longer present
# This probably won't find any *.pyc files, but just in case
$remove = "*.pyc",
"*.chm"
$remove | ForEach-Object {
    Write-Host "Removing unneeded $_ files: " -NoNewline
    $found = Get-ChildItem -Path "$BUILDENV_DIR" -Filter $_ -Recurse
    $found | ForEach-Object {
        Remove-Item -Path "$($_.FullName)" -Recurse -Force
        if ( Test-Path -Path "$($_.FullName)" ) {
            Write-Result "Failed" -ForegroundColor Red
            Write-Host "Failed to remove: $($_.FullName)"
            exit 1
        }
    }
    Write-Result "Success" -ForegroundColor Green
}

#-------------------------------------------------------------------------------
# Set timestamps on Files
#-------------------------------------------------------------------------------

# We're doing this again in this script because we use python above to get the
# build architecture and that adds back some __pycache__ and *.pyc files
Write-Host "Getting commit time stamp: " -NoNewline
[DateTime]$origin = "1970-01-01 00:00:00"
$hash_time = $(git show -s --format=%at)
$time_stamp = $origin.AddSeconds($hash_time)
if ( $hash_time ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Setting time stamp on all files: " -NoNewline
$found = Get-ChildItem -Path $BUILDENV_DIR -Recurse
$found | ForEach-Object {
    $_.CreationTime = $time_stamp
    $_.LastAccessTime = $time_stamp
    $_.LastWriteTime = $time_stamp
}
Write-Result "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Get the estimated size of the installation
#-------------------------------------------------------------------------------
Write-Host "Getting Estimated Installation Size: " -NoNewLine
$estimated_size = [math]::Round(((Get-ChildItem "$BUILDENV_DIR" -Recurse -Force | Measure-Object -Sum Length).Sum / 1kb))
if ( $estimated_size -gt 0 ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Build the Installer
#-------------------------------------------------------------------------------

Write-Host "Building the Installer: " -NoNewline
$installer_name = "Salt-Minion-$Version-Py$($PY_VERSION.Split(".")[0])-$ARCH-Setup.exe"
Start-Process -FilePath $NSIS_BIN `
              -ArgumentList "/DSaltVersion=$Version", `
                            "/DPythonArchitecture=$ARCH", `
                            "/DEstimatedSize=$estimated_size", `
                            "$INSTALLER_DIR\Salt-Minion-Setup.nsi" `
              -Wait -WindowStyle Hidden
if ( Test-Path -Path "$INSTALLER_DIR\$installer_name" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    Write-Host "Failed to find $installer_name in installer directory"
    exit 1
}

#-------------------------------------------------------------------------------
# Move installer to build directory
#-------------------------------------------------------------------------------

if ( ! (Test-Path -Path "$BUILD_DIR") ) {
    New-Item -Path "$BUILD_DIR" -ItemType Directory | Out-Null
}
if ( Test-Path -Path "$BUILD_DIR\$installer_name" ) {
    Write-Host "Backing up existing installer: " -NoNewline
    $new_name = "$installer_name.$( Get-Date -UFormat %s ).bak"
    Move-Item -Path "$BUILD_DIR\$installer_name" `
              -Destination "$BUILD_DIR\$new_name"
    if ( Test-Path -Path "$BUILD_DIR\$new_name" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Moving the Installer: " -NoNewline
Move-Item -Path "$INSTALLER_DIR\$installer_name" -Destination "$BUILD_DIR"
if ( Test-Path -Path "$BUILD_DIR\$installer_name" ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Build NullSoft Installer for Salt Completed" -ForegroundColor Cyan
Write-Host $("=" * 80)
Write-Host "Installer can be found at the following location:"
Write-Host "$BUILD_DIR\$installer_name"
