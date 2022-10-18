<#
.SYNOPSIS
Script that builds Python from source

.DESCRIPTION
This script builds python from Source. It then creates the directory
structure as created by the Python installer in C:\Python##. This includes
all header files, scripts, dlls, library files, and pip.

.EXAMPLE
build_python.ps1 -Version 3.8.13

#>
param(
    [Parameter(Mandatory=$false)]
    [ValidatePattern("^\d{1,2}.\d{1,2}.\d{1,2}$")]
    [ValidateSet(
        #"3.10.5",
        #"3.10.4",
        #"3.10.3",
        #"3.9.13",
        #"3.9.12",
        #"3.9.11",
        "3.8.14",
        "3.8.13",
        "3.8.12",
        "3.8.11",
        "3.8.10"
    )]
    [Alias("v")]
    # The version of Python to be built. Pythonnet only supports up to Python
    # 3.8 for now. Pycurl stopped building wheel files after 7.43.0.5 which
    # supported up to 3.8. So we're pinned to the latest version of Python 3.8.
    # We may have to drop support for pycurl.
    # Default is: 3.8.14
    [String] $Version = "3.8.14",

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
# Start the Script
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Build Python from Source" -ForegroundColor Cyan
Write-Host "- Python Version: $Version"
Write-Host "- Architecture:   $Architecture"
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Global Script Preferences
#-------------------------------------------------------------------------------
# The Python Build script doesn't disable the progress bar. This is a problem
# when trying to add this to CICD so we need to disable it system wide. This
# Adds $ProgressPreference=$false to the Default PowerShell profile so when the
# cpython build script is launched it will not display the progress bar. This
# file will be backed up if it already exists and will be restored at the end
# this script.
if ( Test-Path -Path "$profile" ) {
    if ( ! (Test-Path -Path "$profile.salt_bak") ) {
        Write-Host "Backing up PowerShell Profile: " -NoNewline
        Move-Item -Path "$profile" -Destination "$profile.salt_bak"
        if ( Test-Path -Path "$profile.salt_bak" ) {
            Write-Host "Success" -ForegroundColor Green
        } else {
            Write-Host "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

$CREATED_POWERSHELL_PROFILE_DIRECTORY = $false
if ( ! (Test-Path -Path "$(Split-Path "$profile" -Parent)") ) {
    Write-Host "Creating WindowsPowerShell Directory: " -NoNewline
    New-Item -Path "$(Split-Path "$profile" -Parent)" -ItemType Directory | Out-Null
    if ( Test-Path -Path "$(Split-Path "$profile" -Parent)" ) {
        $CREATED_POWERSHELL_PROFILE_DIRECTORY = $true
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Creating Temporary PowerShell Profile: " -NoNewline
'$ProgressPreference = "SilentlyContinue"' | Out-File -FilePath $profile
'$ErrorActionPreference = "Stop"' | Out-File -FilePath $profile
Write-Host "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------

# Script Variables
$PROJ_DIR     = $(git rev-parse --show-toplevel)

# Python Variables

$PY_DOT_VERSION = $Version
$PY_VERSION     = [String]::Join(".", $Version.Split(".")[0..1])
$PY_SRC_DIR     = "$( (Get-Item $PROJ_DIR).Parent.FullName )\cpython"
$PY_REPO_URL    = "https://github.com/python/cpython"
$PIP_URL        = "https://bootstrap.pypa.io/get-pip.py"
$PYTHON_DIR     = "C:\Python$($PY_VERSION -replace "\.")"
$SCRIPTS_DIR    = "$PYTHON_DIR\Scripts"

if ( $Architecture -eq "x64" ) {
    $PY_BLD_DIR     = "$PY_SRC_DIR\PCbuild\amd64"
    $SALT_DEP_URL   = "https://repo.saltproject.io/windows/dependencies/64"
} else {
    $PY_BLD_DIR     = "$PY_SRC_DIR\PCbuild\win32"
    $SALT_DEP_URL   = "https://repo.saltproject.io/windows/dependencies/32"
}

#-------------------------------------------------------------------------------
# Prepping Environment
#-------------------------------------------------------------------------------
if ( Test-Path -Path "$PY_SRC_DIR" ) {
    Write-Host "Removing existing cpython directory: " -NoNewline
    Remove-Item -Path "$PY_SRC_DIR" -Recurse -Force
    if ( Test-Path -Path "$PY_SRC_DIR" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

if ( Test-Path -Path "$PYTHON_DIR" ) {
    Write-Host "Removing Existing Build Directory ($PYTHON_DIR): " -NoNewline
    Remove-Item -Path "$PYTHON_DIR" -Recurse -Force | Out-Null
    if ( Test-Path -Path "$PYTHON_DIR" ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Success" -ForegroundColor Green
    }
}

#-------------------------------------------------------------------------------
# Building Python
#-------------------------------------------------------------------------------
Write-Host "Cloning Python ($PY_DOT_VERSION): " -NoNewline
$args = "clone", "--depth", "1", "--branch", "v$PY_DOT_VERSION", "$PY_REPO_URL", "$PY_SRC_DIR"
Start-Process -FilePath git `
              -ArgumentList $args `
              -Wait -WindowStyle Hidden
if ( Test-Path -Path "$PY_SRC_DIR\Python") {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Building Python (long-running): " -NoNewLine
# Visual Studio Leaves and MSbuild.exe process hanging around to optimize future
# builds. This causes the build to hang waiting for all processes to end. So, we
# need to disable Node Reuse so it closes the running MSBuild.exe process.
[System.Environment]::SetEnvironmentVariable("MSBUILDDISABLENODEREUSE", "1")
Start-Process -FilePath "$PY_SRC_DIR\PCbuild\build.bat" `
    -ArgumentList "-p", "$Architecture", "--no-tkinter" `
    -WindowStyle Hidden
# Sometimes the process doesn't return properly so the script can continue
# So, we'll run it asynchronously and check for the last file it builds
while ( ! (Test-Path -Path "$PY_BLD_DIR\pythonw.exe") ) {
    Start-Sleep -Seconds 5
}
# Remove the environment variable after build
[System.Environment]::SetEnvironmentVariable("MSBUILDDISABLENODEREUSE", $null)
if ( Test-Path -Path "$PY_BLD_DIR\python.exe") {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Creating Python Directory Structure
#-------------------------------------------------------------------------------
Write-Host "Creating Build Directory ($PYTHON_DIR): " -NoNewline
New-Item -Path "$PYTHON_DIR" -ItemType Directory | Out-Null
if ( Test-Path -Path "$PYTHON_DIR" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Moving Python binaries: " -NoNewline
$binaries = @(
    "py.exe",
    "pyw.exe",
    "python.exe",
    "pythonw.exe",
    "python3.dll",
    "python38.dll",
    "vcruntime140.dll",
    "venvlauncher.exe",
    "venvwlauncher.exe"
)
$binaries | ForEach-Object {
    Move-Item -Path "$PY_BLD_DIR\$_" -Destination "$PYTHON_DIR" | Out-Null
    if ( ! ( Test-Path -Path "$PYTHON_DIR\$_") ) {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Success" -ForegroundColor Green

Write-Host "Creating DLLs directory: " -NoNewline
New-Item -Path "$PYTHON_DIR\DLLs" -ItemType Directory | Out-Null
if ( Test-Path -Path "$PYTHON_DIR\DLLs" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Moving Python DLLS: " -NoNewline
Move-Item -Path "$PY_BLD_DIR\*.pyd" -Destination "$PYTHON_DIR\DLLs"
Move-Item -Path "$PY_BLD_DIR\*.dll" -Destination "$PYTHON_DIR\DLLs"
if ( ! (Test-Path -Path "$PYTHON_DIR\DLLs\select.pyd") ) {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}
if ( Test-Path -Path "$PYTHON_DIR\DLLs\sqlite3.dll" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Copying Header Files: " -NoNewline
Copy-Item -Path "$PY_SRC_DIR\include" -Destination "$PYTHON_DIR\include" -Recurse | Out-Null
Copy-Item -Path "$PY_SRC_DIR\PC\pyconfig.h" -Destination "$PYTHON_DIR\include" -Recurse | Out-Null
if ( ! (Test-Path -Path "$PYTHON_DIR\include\abstract.h") ) {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}
if ( Test-Path -Path "$PYTHON_DIR\include\pyconfig.h" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Copying Library Files: " -NoNewline
Copy-Item -Path "$PY_SRC_DIR\Lib" -Destination "$PYTHON_DIR\Lib" -Recurse | Out-Null
if ( Test-Path -Path "$PYTHON_DIR\Lib\abc.py" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Creating libs directory: " -NoNewline
New-Item -Path "$PYTHON_DIR\libs" -ItemType Directory | Out-Null
if ( Test-Path -Path "$PYTHON_DIR\libs" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Copying lib Files: " -NoNewline
Copy-Item -Path "$PY_BLD_DIR\python3.lib" -Destination "$PYTHON_DIR\libs" | Out-Null
Copy-Item -Path "$PY_BLD_DIR\python38.lib" -Destination "$PYTHON_DIR\libs" | Out-Null
if ( ! (Test-Path -Path "$PYTHON_DIR\libs\python3.lib") ) {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}
if ( Test-Path -Path "$PYTHON_DIR\libs\python38.lib" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Retrieving SSL libaries: " -NoNewline
$libeay_url = "$SALT_DEP_URL/openssl/1.1.1k/libeay32.dll"
$ssleay_url = "$SALT_DEP_URL/openssl/1.1.1k/ssleay32.dll"
Invoke-WebRequest -Uri "$libeay_url" -OutFile "$PYTHON_DIR\libeay32.dll" | Out-Null
Invoke-WebRequest -Uri "$ssleay_url" -OutFile "$PYTHON_DIR\ssleay32.dll" | Out-Null
if ( ! (Test-Path -Path "$PYTHON_DIR\libeay32.dll") ) {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}
if ( Test-Path -Path "$PYTHON_DIR\ssleay32.dll" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Installing PIP
#-------------------------------------------------------------------------------
Write-Host "Downloading pip: " -NoNewline
Invoke-WebRequest -Uri $PIP_URL -OutFile "$env:TEMP\get-pip.py" | Out-Null
if ( Test-Path -Path "$env:TEMP\get-pip.py" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Installing pip: " -NoNewline
Start-Process -FilePath "$PYTHON_DIR\python.exe" `
    -ArgumentList "$env:TEMP\get-pip.py" `
    -Wait -WindowStyle Hidden
if ( Test-Path -Path "$PYTHON_DIR\Scripts\pip.exe" ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Removing Unneeded files from Python
#-------------------------------------------------------------------------------
Write-Host "Removing Unneeded Files from Python: " -NoNewline
$remove = "idlelib",
          "test",
          "tkinter",
          "turtledemo"
$remove | ForEach-Object {
    Remove-Item -Path "$PYTHON_DIR\Lib\$_" -Recurse -Force
    if ( Test-Path -Path "$PYTHON_DIR\Lib\$_" ) {
        Write-Host "Failed" -ForegroundColor Red
        Write-Host "Failed to remove: $PYTHON_DIR\Lib\$_"
        exit 1
    }
}
Write-Host "Success" -ForegroundColor Green

#-------------------------------------------------------------------------------
# Updating PATH Environment Variable
#-------------------------------------------------------------------------------
Write-Host "Updating Path: " -NoNewLine
$Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
if ( ! ($Path.ToLower().Contains("$SCRIPTS_DIR".ToLower())) ) {
    $env:Path = "$PYTHON_DIR;$SCRIPTS_DIR;$Path"
    [Environment]::SetEnvironmentVariable("Path", $env:Path, "Machine")
}

$Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
if ( ! ($Path.ToLower().Contains("$PYTHON_DIR".ToLower())) ) {
    Write-Host "Failed" -ForegroundColor Red
    Write-Host "Failed to add $PYTHON_DIR to path"
    exit 1
}
if ( $Path.ToLower().Contains("$SCRIPTS_DIR".ToLower()) ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    Write-Host "Failed to add $SCRIPTS_DIR to path"
    exit 1
}

if ( $CREATED_POWERSHELL_PROFILE_DIRECTORY ) {
    Write-Host "Removing PowerShell Profile Directory"
    Remove-Item -Path "$(Split-Path "$profile" -Parent)" -Recurse -Force
    if ( !  (Test-Path -Path "$(Split-Path "$profile" -Parent)") ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failure" -ForegroundColor Red
        exit 1
    }
}

if ( Test-Path -Path "$profile" ) {
    Write-Host "Removing Temporary PowerShell Profile: " -NoNewline
    Remove-Item -Path "$profile" -Force
    if ( ! (Test-Path -Path "$profile") ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

if ( Test-Path -Path "$profile.salt_bak" ) {
    Write-Host "Restoring Original PowerShell Profile: " -NoNewline
    Move-Item -Path "$profile.salt_bak" -Destination "$profile"
    if ( Test-Path -Path "$profile" ) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Host "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Adding Registry Key for Python Launcher
#-------------------------------------------------------------------------------
Write-Host "Writing Python Launcher Registry Entries: " -NoNewline
$PL_REG = "HKLM:\SOFTWARE\Python\PythonCore\$PY_VERSION\InstallPath"
New-Item -Path $PL_REG -Value $PYTHON_DIR -Force | Out-Null
if ( Test-Path -Path $PL_REG ) {
    Write-Host "Success" -ForegroundColor Green
} else {
    Write-Host "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------
Write-Host $("-" * 80)
Write-Host "Build Python $Architecture from Source Completed" `
    -ForegroundColor Cyan
Write-Host "Environment Location: $PYTHON_DIR"
Write-Host $("=" * 80)
