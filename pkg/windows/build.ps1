<#
.SYNOPSIS
Parent script that runs all other scripts required to build Salt

.DESCRIPTION
This script Cleans, Installs Dependencies, Builds Python, Installs Salt,
and builds the NullSoft Installer. It depends on the following Scripts
and are called in this order:

- clean_env.ps1
- install_nsis.ps1
- build_python.ps1
- install_salt.ps1
- build_pkg.ps1

.EXAMPLE
build.ps1

.EXAMPLE
build.ps1 -Version 3005 -PythonVersion 3.10.9

#>

param(
    [Parameter(Mandatory=$false)]
    [Alias("v")]
    # The version of Salt to be built. If this is not passed, the script will
    # attempt to get it from the git describe command on the Salt source
    # repo
    [String] $Version,

    [Parameter(Mandatory=$false)]
    [ValidateSet("x86", "x64", "amd64")]
    [Alias("a")]
    # The System Architecture to build. "x86" will build a 32-bit installer.
    # "x64" will build a 64-bit installer. Default is: x64
    $Architecture = "x64",

    [Parameter(Mandatory=$false)]
    [ValidatePattern("^\d{1,2}.\d{1,2}.\d{1,2}$")]
    [Alias("p")]
    # The version of Python to build/fetch. This is tied to the version of
    # Relenv
    [String] $PythonVersion,

    [Parameter(Mandatory=$false)]
    [Alias("r")]
    # The version of Relenv to install
    [String] $RelenvVersion,

    [Parameter(Mandatory=$false)]
    [Alias("b")]
    # Build python from source instead of fetching a tarball
    # Requires VC Build Tools
    [Switch] $Build,

    [Parameter(Mandatory=$false)]
    [Alias("c")]
    # Don't pretify the output of the Write-Result
    [Switch] $CICD,

    [Parameter(Mandatory=$false)]
    # Don't install/build python. It should already be installed
    [Switch] $SkipInstall

)

#-------------------------------------------------------------------------------
# Script Preferences
#-------------------------------------------------------------------------------

$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"

#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
$SCRIPT_DIR     = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$PROJECT_DIR    = $(git rev-parse --show-toplevel)

if ( $Architecture -eq "amd64" ) {
  $Architecture = "x64"
}

#-------------------------------------------------------------------------------
# Verify Salt and Version
#-------------------------------------------------------------------------------

if ( [String]::IsNullOrEmpty($Version) ) {
    if ( ! (Test-Path -Path $PROJECT_DIR) ) {
        Write-Host "Missing Salt Source Directory: $PROJECT_DIR"
        exit 1
    }
    Push-Location $PROJECT_DIR
    $Version = $( git describe )
    $Version = $Version.Trim("v")
    Pop-Location
    if ( [String]::IsNullOrEmpty($Version) ) {
        Write-Host "Failed to get version from $PROJECT_DIR"
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Verify Python and Relenv Versions
#-------------------------------------------------------------------------------

$yaml = Get-Content -Path "$PROJECT_DIR\cicd\shared-gh-workflows-context.yml"
$dict_versions = @{}
$dict_versions["python_version"]=($yaml | Select-String -Pattern "python_version: (.*)").matches.groups[1].Value.Trim("""")
$dict_versions["relenv_version"]=($yaml | Select-String -Pattern "relenv_version: (.*)").matches.groups[1].Value.Trim("""")

if ( [String]::IsNullOrEmpty($PythonVersion) ) {
    $PythonVersion = $dict_versions["python_version"]
    if ( [String]::IsNullOrEmpty($PythonVersion) ) {
        Write-Host "Failed to load Python Version"
        exit 1
    }
}

if ( [String]::IsNullOrEmpty($RelenvVersion) ) {
    $RelenvVersion = $dict_versions["relenv_version"]
    if ( [String]::IsNullOrEmpty($RelenvVersion) ) {
        Write-Host "Failed to load Relenv Version"
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("#" * 80)
Write-Host "Build Salt Installer Packages" -ForegroundColor Cyan
Write-Host "- Salt Version:   $Version"
Write-Host "- Python Version: $PythonVersion"
Write-Host "- Relenv Version: $RelenvVersion"
Write-Host "- Architecture:   $Architecture"
Write-Host $("v" * 80)

#-------------------------------------------------------------------------------
# Install NSIS
#-------------------------------------------------------------------------------

$KeywordArguments = @{}
if ( $CICD ) {
    $KeywordArguments["CICD"] = $true
}
& "$SCRIPT_DIR\install_nsis.ps1" @KeywordArguments
if ( ! $? ) {
    Write-Host "Failed to install NSIS"
    exit 1
}

#-------------------------------------------------------------------------------
# Install WIX
#-------------------------------------------------------------------------------

$KeywordArguments = @{}
if ( $CICD ) {
    $KeywordArguments["CICD"] = $true
}
& "$SCRIPT_DIR\install_wix.ps1" @KeywordArguments
if ( ! $? ) {
    Write-Host "Failed to install WIX"
    exit 1
}

#-------------------------------------------------------------------------------
# Install Visual Studio Build Tools
#-------------------------------------------------------------------------------

$KeywordArguments = @{}
if ( $CICD ) {
    $KeywordArguments["CICD"] = $true
}
& "$SCRIPT_DIR\install_vs_buildtools.ps1" @KeywordArguments
if ( ! $? ) {
    Write-Host "Failed to install Visual Studio Build Tools"
    exit 1
}


if ( ! $SkipInstall ) {
  #-------------------------------------------------------------------------------
  # Build Python
  #-------------------------------------------------------------------------------

  $KeywordArguments = @{
      Version = $PythonVersion
      Architecture = $Architecture
      RelenvVersion = $RelenvVersion
  }
  if ( $Build ) {
      $KeywordArguments["Build"] = $false
  }
  if ( $CICD ) {
      $KeywordArguments["CICD"] = $true
  }

  & "$SCRIPT_DIR\build_python.ps1" @KeywordArguments
  if ( ! $? ) {
      Write-Host "Failed to build Python"
      exit 1
  }
}

#-------------------------------------------------------------------------------
# Install Salt
#-------------------------------------------------------------------------------

$KeywordArguments = @{}
if ( $CICD ) {
    $KeywordArguments["CICD"] = $true
}
if ( $SkipInstall ) {
    $KeywordArguments["SkipInstall"] = $true
}
$KeywordArguments["PKG"] = $true
& "$SCRIPT_DIR\install_salt.ps1" @KeywordArguments
if ( ! $? ) {
    Write-Host "Failed to install Salt"
    exit 1
}

#-------------------------------------------------------------------------------
# Prep Salt for Packaging
#-------------------------------------------------------------------------------

$KeywordArguments = @{}
if ( $CICD ) {
    $KeywordArguments["CICD"] = $true
}
$KeywordArguments["PKG"] = $true
& "$SCRIPT_DIR\prep_salt.ps1" @KeywordArguments
if ( ! $? ) {
    Write-Host "Failed to Prepare Salt for packaging"
    exit 1
}

#-------------------------------------------------------------------------------
# Build NSIS Package
#-------------------------------------------------------------------------------

$KeywordArguments = @{}
if ( ! [String]::IsNullOrEmpty($Version) ) {
    $KeywordArguments.Add("Version", $Version)
}
if ( $CICD ) {
    $KeywordArguments["CICD"] = $true
}

& "$SCRIPT_DIR\nsis\build_pkg.ps1" @KeywordArguments

if ( ! $? ) {
    Write-Host "Failed to build NSIS package"
    exit 1
}

#-------------------------------------------------------------------------------
# Build MSI Package
#-------------------------------------------------------------------------------

& "$SCRIPT_DIR\msi\build_pkg.ps1" @KeywordArguments

if ( ! $? ) {
    Write-Host "Failed to build NSIS package"
    exit 1
}

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------

Write-Host $("^" * 80)
Write-Host "Build Salt $Architecture Completed" -ForegroundColor Cyan
Write-Host $("#" * 80)
