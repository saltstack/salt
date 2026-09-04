<#
.SYNOPSIS
Script that sets up the environment for testing

.DESCRIPTION
This script creates the directory structure and files needed build a mock salt
installer for testing

.EXAMPLE
setup.ps1
#>
param(
    [Parameter(Mandatory=$false)]
    [Alias("c")]
# Don't prettify the output of the Write-Result
    [Switch] $CICD
)

#-------------------------------------------------------------------------------
# Script Preferences
#-------------------------------------------------------------------------------

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

$PROJECT_DIR   = $(git rev-parse --show-toplevel)
$SCRIPT_DIR    = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$WINDOWS_DIR   = "$PROJECT_DIR\pkg\windows"
$NSIS_DIR      = "$WINDOWS_DIR\nsis"
$BUILDENV_DIR  = "$WINDOWS_DIR\buildenv"
$PREREQS_DIR   = "$WINDOWS_DIR\prereqs"
$NSIS_BIN      = "$( ${env:ProgramFiles(x86)} )\NSIS\makensis.exe"
$SALT_DEP_URL  = "https://github.com/saltstack/salt-windows-deps/raw/refs/heads/main/ssm/64/"
$GO_DEPS_URL   = "https://github.com/saltstack/salt-windows-deps/raw/refs/heads/main/go"

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Build Test Environment for NSIS Tests" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Setup Directories
#-------------------------------------------------------------------------------

$directories = "$PREREQS_DIR",
               "$BUILDENV_DIR",
               "$BUILDENV_DIR\configs"
$directories | ForEach-Object {
    if ( ! (Test-Path -Path "$_") ) {
        Write-Host "Creating $_`: " -NoNewline
        New-Item -Path $_ -ItemType Directory | Out-Null
        if ( Test-Path -Path "$_" ) {
            Write-Result "Success"
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

#-------------------------------------------------------------------------------
# Go (required to build test stubs)
#-------------------------------------------------------------------------------

Write-Host "Looking for Go 1.20+: " -NoNewline
$go_ok = $false
$go_exe = (Get-Command go -ErrorAction SilentlyContinue)
if ( -not $go_exe ) {
    # Go may be installed but not yet in the current session PATH.
    # Check both common install locations (1.21+ default, then pre-1.21).
    $known_paths = @("C:\Program Files\Go\bin\go.exe", "C:\Go\bin\go.exe")
    foreach ( $p in $known_paths ) {
        if ( Test-Path $p ) {
            $env:PATH = "$(Split-Path $p);$env:PATH"
            $go_exe = Get-Command go -ErrorAction SilentlyContinue
            break
        }
    }
}
if ( $go_exe ) {
    $ver_out = & go version 2>$null
    if ( $ver_out -match 'go(\d+)\.(\d+)' ) {
        $maj = [int]$Matches[1]; $min = [int]$Matches[2]
        if ( $maj -gt 1 -or ($maj -eq 1 -and $min -ge 20) ) {
            $go_ok = $true
        }
    }
}
if ( $go_ok ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Missing" -ForegroundColor Yellow

    Write-Host "Downloading Go: " -NoNewline
    $url  = "$GO_DEPS_URL/go1.26.1.windows-amd64.msi"
    $file = "$env:TEMP\go-install.msi"
    Invoke-WebRequest -Uri $url -OutFile "$file"
    if ( Test-Path -Path "$file" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Installing Go: " -NoNewline
    Start-Process "msiexec.exe" -ArgumentList "/i `"$file`" /quiet /norestart" -Wait -NoNewWindow
    if ( Test-Path -Path "C:\Program Files\Go\bin\go.exe" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }

    # Refresh session PATH so go build works immediately without reopening the shell
    $env:PATH = "C:\Program Files\Go\bin;$env:PATH"

    Write-Host "Cleaning up: " -NoNewline
    Remove-Item -Path $file -Force
    if ( ! (Test-Path -Path "$file") ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Yellow
    }
}

#-------------------------------------------------------------------------------
# Create binaries
#-------------------------------------------------------------------------------

# Build the daemon stub (salt-minion.exe): a real PE that stays alive and
# exits cleanly on CTRL_C so NSSM can manage it as a proper service.
# -C changes the working directory to the module root before building so
# that Go modules can locate go.mod (requires Go 1.20+).
Write-Host "Building salt-minion.exe stub: " -NoNewline
& go build -C "$SCRIPT_DIR\stubs\daemon" -o "$BUILDENV_DIR\salt-minion.exe" .
if ( Test-Path -Path "$BUILDENV_DIR\salt-minion.exe" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

# Build the exit stub (vcredist): a real PE that exits immediately with code 0
# so ExecWait succeeds and the installer does not abort during VCRedist install.
$prereq_files = "vcredist_x86_2022.exe",
                "vcredist_x64_2022.exe"
$prereq_files | ForEach-Object {
    Write-Host "Building $_`: " -NoNewline
    & go build -C "$SCRIPT_DIR\stubs\exit" -o "$PREREQS_DIR\$_" .
    if ( Test-Path -Path "$PREREQS_DIR\$_" ) {
        Write-Result "Success"
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

# python.exe only needs to exist on disk (checked by test assertions, not executed)
$binary_files = @("python.exe")
$binary_files | ForEach-Object {
    Write-Host "Creating $_`: " -NoNewline
    Set-Content -Path "$BUILDENV_DIR\$_" -Value "binary"
    if ( Test-Path -Path "$BUILDENV_DIR\$_" ) {
        Write-Result "Success"
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

# Make sure ssm.exe is present. This is needed for VMtools
if ( ! (Test-Path -Path "$BUILDENV_DIR\ssm.exe") ) {
    Write-Host "Copying SSM to Build Env: " -NoNewline
    Invoke-WebRequest -Uri "$SALT_DEP_URL/ssm-2.24-103-gdee49fc.exe" -OutFile "$BUILDENV_DIR\ssm.exe"
    if ( Test-Path -Path "$BUILDENV_DIR\ssm.exe" ) {
        Write-Result "Success" -ForegroundColor Green
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Copy Configs
#-------------------------------------------------------------------------------

Write-Host "Copy testing minion config: " -NoNewline
Copy-Item -Path "$NSIS_DIR\tests\_files\minion" `
          -Destination "$BUILDENV_DIR\configs\"
if ( Test-Path -Path "$BUILDENV_DIR\configs\minion" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Build mock installer
#-------------------------------------------------------------------------------
Write-Host "Building mock installer: " -NoNewline
Start-Process -FilePath $NSIS_BIN `
              -ArgumentList "/DSaltVersion=test", `
                            "/DPythonArchitecture=AMD64", `
                            "$NSIS_DIR\installer\Salt-Minion-Setup.nsi" `
              -Wait -WindowStyle Hidden
$installer = "$NSIS_DIR\installer\Salt-Minion-test-Py3-AMD64-Setup.exe"
if ( Test-Path -Path "$installer" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    Write-Host "$NSIS_BIN /DSaltVersion=test /DPythonArchitecture=AMD64 $NSIS_DIR\installer\Salt-Minion-Setup.nsi"
    exit 1
}

Write-Host "Moving mock installer: " -NoNewline
$test_installer = "$NSIS_DIR\tests\test-setup.exe"
Move-Item -Path $installer -Destination "$test_installer" -Force
if ( Test-Path -Path "$test_installer" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Setup pytest
#-------------------------------------------------------------------------------

Write-Host "Setting up venv: " -NoNewline
python.exe -m venv "$SCRIPT_DIR\venv"
if ( Test-Path -Path "$SCRIPT_DIR\venv" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Activating venv: " -NoNewline
& $SCRIPT_DIR\venv\Scripts\activate.ps1
if ( "$env:VIRTUAL_ENV" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

$pip_modules = "pytest",
               "pytest-helpers-namespace",
               "psutil"
$pip_modules | ForEach-Object {
    Write-Host "Installing $_`: " -NoNewline
    Start-Process -FilePath pip `
                  -ArgumentList "install", "$_" `
                  -Wait -WindowStyle Hidden
    if ($( pip show $_ ) -contains "Name: $_") {
        Write-Result "Success"
    } else {
        Write-Result "Failed" -ForegroundColor Red
        exit 1
    }
}

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Build Test Environment for NSIS Tests Complete" -ForegroundColor Cyan
Write-Host $("=" * 80)
