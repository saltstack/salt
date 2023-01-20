<#
.SYNOPSIS
This script builds the MSI installer

.DESCRIPTION
This script builds the MSI installer from the contents of the buildenv directory

.EXAMPLE
build_pkg.ps1

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

function VerifyOrDownload ($local_file, $URL, $SHA256) {
    #### Verify or download file
    $filename = Split-Path $local_file -leaf
    if ( Test-Path -Path $local_file ) {
        Write-Host "Verifying hash for $filename`: " -NoNewline
        if ( (Get-FileHash $local_file).Hash -eq $SHA256 ) {
            Write-Result "Verified" -ForegroundColor Green
            return
        } else {
            Write-Result "Failed Hash" -ForegroundColor Red
            Remove-Item -Path $local_file -Force
        }
    }
    Write-Host "Downloading $filename`: " -NoNewline
    Invoke-WebRequest -Uri "$URL" -OutFile "$local_file"
    if ( Test-Path -Path $local_file ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------

$WEBCACHE_DIR = "$env:TEMP\msi_build_cache_dir"
$DEPS_URL     = "http://repo.saltproject.io/windows/dependencies"
$PROJECT_DIR  = $(git rev-parse --show-toplevel)
$BUILD_DIR    = "$PROJECT_DIR\pkg\windows\build"
$BUILDENV_DIR = "$PROJECT_DIR\pkg\windows\buildenv"
$SCRIPTS_DIR  = "$BUILDENV_DIR\Scripts"
$PYTHON_BIN   = "$SCRIPTS_DIR\python.exe"
$BUILD_ARCH   = $(. $PYTHON_BIN -c "import platform; print(platform.architecture()[0])")
$SCRIPT_DIR   = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$RUNTIME_DIR  = [System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()
$CSC_BIN      = "$RUNTIME_DIR\csc.exe"

if ( $BUILD_ARCH -eq "64bit" ) {
    $BUILD_ARCH    = "AMD64"
} else {
    $BUILD_ARCH    = "x86"
}
# MSBuild needed to compile C#
if ( [System.IntPtr]::Size -eq 8 ) {
    $MSBUILD = "C:\Program Files (x86)\MSBuild\14.0"
} else {
    $MSBUILD = "C:\Program Files\MSBuild\14.0"
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
# Script Begin
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Build MSI Installer for Salt" -ForegroundColor Cyan
Write-Host "- Architecture: $BUILD_ARCH"
Write-Host "- Salt Version: $Version"
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Ensure cache dir exists
#-------------------------------------------------------------------------------

if ( ! (Test-Path -Path $WEBCACHE_DIR) ) {
    Write-Host "Creating cache directory: " -NoNewline
    New-Item -ItemType directory -Path $WEBCACHE_DIR | Out-Null
    if ( Test-Path -Path $WEBCACHE_DIR ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Ensure WIX environment variable is set, if not refresh and check again
#-------------------------------------------------------------------------------
# If wix is installed in the same session, the WIX environment variable won't be
# defined. If it still fails, WIX may not be installed, or the WIX environment
# variable may not be defined.
if ( ! "$env:WIX" ) {
    Write-Host "Updating environment variables (wix): " -NoNewline
    foreach ($level in "Machine", "User") {
        $vars = [Environment]::GetEnvironmentVariables($level).GetEnumerator()
        $vars | ForEach-Object { $_ } | Set-Content -Path { "Env:$( $_.Name )" }
    }
    if ( "$env:WIX" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Caching VC++ Runtimes
#-------------------------------------------------------------------------------

$RUNTIMES = @(
    ("Microsoft_VC120_CRT_x64.msm", "64", "15FD10A495287505184B8913DF8D6A9CA461F44F78BC74115A0C14A5EDD1C9A7"),
    ("Microsoft_VC120_CRT_x86.msm", "32", "26340B393F52888B908AC3E67B935A80D390E1728A31FF38EBCEC01117EB2579"),
    ("Microsoft_VC140_CRT_x64.msm", "64", "E1344D5943FB2BBB7A56470ED0B7E2B9B212CD9210D3CC6FA82BC3DA8F11EDA8"),
    ("Microsoft_VC140_CRT_x86.msm", "32", "0D36CFE6E9ABD7F530DBAA4A83841CDBEF9B2ADCB625614AF18208FDCD6B92A4")
)
$RUNTIMES | ForEach-Object {
    $name, $arch, $hash = $_
    VerifyOrDownload "$WEBCACHE_DIR\$name" "$DEPS_URL/$arch/$name" "$hash"
}

#-------------------------------------------------------------------------------
# Converting to MSI Version
#-------------------------------------------------------------------------------

Write-Host "Getting internal version: " -NoNewline
[regex]$tagRE = '(?:[^\d]+)?(?<major>[\d]{1,4})(?:\.(?<minor>[\d]{1,2}))?(?:\.(?<bugfix>[\d]{0,2}))?'
$tagREM = $tagRE.Match($Version)
$major  = $tagREM.groups["major"].ToString()
$minor  = $tagREM.groups["minor"]
$bugfix = $tagREM.groups["bugfix"]
if ([string]::IsNullOrEmpty($minor)) {$minor = 0}
if ([string]::IsNullOrEmpty($bugfix)) {$bugfix = 0}
# Assumption: major is a number
$major1 = $major.substring(0, 2)
$major2 = $major.substring(2)
$INTERNAL_VERSION = "$major1.$major2.$minor"
Write-Result $INTERNAL_VERSION -ForegroundColor Green

#-------------------------------------------------------------------------------
# Setting Product Variables
#-------------------------------------------------------------------------------

$MANUFACTURER        = "Salt Project"
$PRODUCT             = "Salt Minion"
$PRODUCTFILE         = "Salt-Minion-$Version"
$PRODUCTDIR          = "Salt"
$DISCOVER_INSTALLDIR = "$BUILDENV_DIR", "$BUILDENV_DIR"
$DISCOVER_CONFDIR    = Get-Item "$BUILDENV_DIR\configs"

# MSI related arrays for 64 and 32 bit values, selected by BUILD_ARCH
if ($BUILD_ARCH -eq "AMD64") {$i = 0} else {$i = 1}
$WIN64        = "yes",                  "no"                   # Used in wxs
$ARCHITECTURE = "x64",                  "x86"                  # WiX dictionary values
$ARCH_AKA     = "AMD64",                "x86"                  # For filename
$PROGRAMFILES = "ProgramFiles64Folder", "ProgramFilesFolder"   # msi dictionary values

function CheckExitCode() {   # Exit on failure
    if ($LastExitCode -ne 0) {
        Write-Result "Failed" -ForegroundColor Red
        if (Test-Path build.tmp -PathType Leaf) {
            Get-Content build.tmp
            Remove-Item build.tmp
        }
        exit(1)
    }
    Write-Result "Success" -ForegroundColor Green
    if (Test-Path build.tmp -PathType Leaf) {
        Remove-Item build.tmp
    }
}

#-------------------------------------------------------------------------------
# Compiling .cs to .dll
#-------------------------------------------------------------------------------

Write-Host "Compiling *.cs to *.dll: " -NoNewline
# Compiler options are exactly those of a wix msbuild project.
# https://docs.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-options
& "$CSC_BIN" /nologo `
    /noconfig /nostdlib+ /errorreport:prompt /warn:4 /define:TRACE /highentropyva- `
    /debug:pdbonly /filealign:512 /optimize+ /target:library /utf8output `
    /reference:"$($ENV:WIX)SDK\Microsoft.Deployment.WindowsInstaller.dll" `
    /reference:"$($ENV:WIX)bin\wix.dll" `
    /reference:"C:\Windows\Microsoft.NET\Framework\v2.0.50727\mscorlib.dll" `
    /reference:"C:\Windows\Microsoft.NET\Framework\v2.0.50727\System.dll" `
    /reference:"C:\Windows\Microsoft.NET\Framework\v2.0.50727\System.Xml.dll" `
    /reference:"C:\Windows\Microsoft.NET\Framework\v2.0.50727\System.ServiceProcess.dll" `
    /reference:"C:\Windows\Microsoft.NET\Framework\v2.0.50727\System.Management.dll" `
    /nowarn:"1701,1702" `
    /out:"$SCRIPT_DIR\CustomAction01\CustomAction01.dll" `
    "$SCRIPT_DIR\CustomAction01\CustomAction01.cs" `
    "$SCRIPT_DIR\CustomAction01\CustomAction01Util.cs" `
    "$SCRIPT_DIR\CustomAction01\Properties\AssemblyInfo.cs"
CheckExitCode

#-------------------------------------------------------------------------------
# Packaging Sandbox DLLs
#-------------------------------------------------------------------------------

Write-Host "Packaging *.dll's to *.CA.dll: " -NoNewline
# MakeSfxCA creates a self-extracting managed MSI CA DLL because
# The custom action DLL will run in a sandbox and needs all DLLs inside. This adds 700 kB.
# Because MakeSfxCA cannot check if Wix will reference a non existing procedure, you must double check yourself.
# Usage: MakeSfxCA <outputca.dll> SfxCA.dll <inputca.dll> [support files ...]
& "$($ENV:WIX)sdk\MakeSfxCA.exe" `
    "$SCRIPT_DIR\CustomAction01\CustomAction01.CA.dll" `
    "$($ENV:WIX)sdk\x86\SfxCA.dll" `
    "$SCRIPT_DIR\CustomAction01\CustomAction01.dll" `
    "$($ENV:WIX)SDK\Microsoft.Deployment.WindowsInstaller.dll" `
    "$($ENV:WIX)bin\wix.dll" `
    "$($ENV:WIX)bin\Microsoft.Deployment.Resources.dll" `
    "$SCRIPT_DIR\CustomAction01\CustomAction.config" > build.tmp
CheckExitCode

# move conf folder up one dir because it must not be discovered twice and xslt is difficult
Write-Host "Remove configs from discovery: " -NoNewline
Move-Item -Path "$DISCOVER_CONFDIR" `
          -Destination "$($DISCOVER_CONFDIR.Parent.Parent.FullName)\temporarily_moved_conf_folder"
CheckExitCode

Write-Host "Discovering install files: " -NoNewline
# https://wixtoolset.org/documentation/manual/v3/overview/heat.html
# -cg <ComponentGroupName> Component group name (cannot contain spaces e.g -cg MyComponentGroup).
# -sfrag   Suppress generation of fragments for directories and components.
# -var     WiX variable for SourceDir
# -gg      Generate guids now. All components are given a guid when heat is run.
# -sfrag   Suppress generation of fragments for directories and components.
# -sreg    Suppress registry harvesting.
# -srd     Suppress harvesting the root directory as an element.
# -ke      Keep empty directories.
# -dr <DirectoryName>   Directory reference to root directories (cannot contains spaces e.g. -dr MyAppDirRef).
# -t <xsl> Transform harvested output with XSL file.
# Selectively delete Guid ,so files remain on uninstall.
& "$($ENV:WIX)bin\heat" dir "$($DISCOVER_INSTALLDIR[$i])" `
    -out "$SCRIPT_DIR\Product-discovered-files-$($ARCHITECTURE[$i]).wxs" `
    -cg DiscoveredBinaryFiles `
    -var var.DISCOVER_INSTALLDIR `
    -dr INSTALLDIR `
    -t "$SCRIPT_DIR\Product-discover-files.xsl" `
    -nologo -indent 1 -gg -sfrag -sreg -srd -ke -template fragment
CheckExitCode

# Move the configs back
Write-Host "Restore configs for installation: " -NoNewline
Move-Item -Path "$($DISCOVER_CONFDIR.Parent.Parent.FullName)\temporarily_moved_conf_folder" `
          -Destination "$DISCOVER_CONFDIR"
CheckExitCode

# TODO: Config shall remain, so delete all Guid
Write-Host "Discovering config files: " -NoNewline
& "$($ENV:WIX)bin\heat" dir "$DISCOVER_CONFDIR" `
    -out "$SCRIPT_DIR\Product-discovered-files-config.wxs" `
    -cg DiscoveredConfigFiles `
    -var var.DISCOVER_CONFDIR `
    -dr CONFDIR `
    -t "$SCRIPT_DIR\Product-discover-files-config.xsl" `
    -nologo -indent 1 -gg -sfrag -sreg -srd -ke -template fragment
CheckExitCode

Write-Host "Compiling *.wxs to $($ARCHITECTURE[$i]) *.wixobj: " -NoNewline
# Options see "%wix%bin\candle"
Push-Location $SCRIPT_DIR
& "$($ENV:WIX)bin\candle.exe" -nologo -sw1150 `
    -arch $ARCHITECTURE[$i] `
    -dWIN64="$($WIN64[$i])" `
    -dPROGRAMFILES="$($PROGRAMFILES[$i])" `
    -dMANUFACTURER="$MANUFACTURER" `
    -dPRODUCT="$PRODUCT" `
    -dPRODUCTDIR="$PRODUCTDIR" `
    -dDisplayVersion="$Version" `
    -dInternalVersion="$INTERNAL_VERSION" `
    -dDISCOVER_INSTALLDIR="$($DISCOVER_INSTALLDIR[$i])" `
    -dWEBCACHE_DIR="$WEBCACHE_DIR" `
    -dDISCOVER_CONFDIR="$DISCOVER_CONFDIR" `
    -ext "$($ENV:WIX)bin\WixUtilExtension.dll" `
    -ext "$($ENV:WIX)bin\WixUIExtension.dll" `
    -ext "$($ENV:WIX)bin\WixNetFxExtension.dll" `
    "$SCRIPT_DIR\Product.wxs" `
    "$SCRIPT_DIR\Product-discovered-files-$($ARCHITECTURE[$i]).wxs" `
    "$SCRIPT_DIR\Product-discovered-files-config.wxs" > build.tmp
CheckExitCode
Pop-Location

Write-Host "Linking $PRODUCT-$INTERNAL_VERSION-$($ARCH_AKA[$i]).msi: " -NoNewline
# Options https://wixtoolset.org/documentation/manual/v3/overview/light.html
# Supress LGHT1076 ICE82 warnings caused by the VC++ Runtime merge modules
#     https://sourceforge.net/p/wix/mailman/message/22945366/
$installer_name = "$PRODUCTFILE-Py3-$($ARCH_AKA[$i]).msi"
& "$($ENV:WIX)bin\light" `
    -nologo -spdb -sw1076 -sice:ICE03 -cultures:en-us `
    -out "$SCRIPT_DIR\$installer_name" `
    -dDISCOVER_INSTALLDIR="$($DISCOVER_INSTALLDIR[$i])" `
    -dDISCOVER_CONFDIR="$DISCOVER_CONFDIR" `
    -ext "$($ENV:WIX)bin\WixUtilExtension.dll" `
    -ext "$($ENV:WIX)bin\WixUIExtension.dll" `
    -ext "$($ENV:WIX)bin\WixNetFxExtension.dll" `
    "$SCRIPT_DIR\Product.wixobj" `
    "$SCRIPT_DIR\Product-discovered-files-$($ARCHITECTURE[$i]).wixobj" `
    "$SCRIPT_DIR\Product-discovered-files-config.wixobj"
CheckExitCode

Remove-Item *.wixobj

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
Move-Item -Path "$SCRIPT_DIR\$installer_name" -Destination "$BUILD_DIR"
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
Write-Host "Build MSI Installer for Salt Complete" -ForegroundColor Cyan
Write-Host $("=" * 80)
