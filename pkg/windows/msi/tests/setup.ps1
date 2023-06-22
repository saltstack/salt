# Set up the environment for testing

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------

$PROJECT_DIR  = $(git rev-parse --show-toplevel)
$SCRIPT_DIR   = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$BUILD_DIR    = "$PROJECT_DIR\pkg\windows\build"
$BUILDENV_DIR = "$PROJECT_DIR\pkg\windows\buildenv"
$MSI_DIR      = "$PROJECT_DIR\pkg\windows\msi"
$BUILD_SCRIPT = "$MSI_DIR\build_pkg.ps1"

#-------------------------------------------------------------------------------
# Script Functions
#-------------------------------------------------------------------------------

function Write-Result($result, $ForegroundColor="Green") {
    $position = 80 - $result.Length - [System.Console]::CursorLeft
    Write-Host -ForegroundColor $ForegroundColor ("{0,$position}$result" -f "")
}

#-------------------------------------------------------------------------------
# Script Begin
#-------------------------------------------------------------------------------

Write-Host $("=" * 80)
Write-Host "Prepare the Test Environment" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Create Mock Directories
#-------------------------------------------------------------------------------

Write-Host "Creating mock build directory: " -NoNewline
New-Item -Path $BUILD_DIR -ItemType Directory | Out-Null
if ( Test-Path -Path $BUILD_DIR ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

Write-Host "Creating mock buildenv directory: " -NoNewline
New-Item -Path $BUILDENV_DIR -ItemType Directory | Out-Null
if ( Test-Path -Path $BUILDENV_DIR ) {
    Write-Result "Success" -ForegroundColor Green
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Copy Mock Files
#-------------------------------------------------------------------------------

Write-Host "Copying mock files: " -NoNewLine
Copy-Item -Path        "$SCRIPT_DIR\_mock_files\buildenv\*" `
          -Destination "$BUILDENV_DIR\" `
          -Recurse -Force | Out-Null
if ( Test-Path -Path "$BUILDENV_DIR\salt-minion.exe" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Build Test MSI
#-------------------------------------------------------------------------------

Write-Host "Building test MSI: " -NoNewLine
. "$BUILD_SCRIPT" | Out-Null
if ( Test-Path -Path "$BUILD_DIR\*.msi" ) {
    Write-Result "Success"
} else {
    Write-Result "Failed" -ForegroundColor Red
    exit 1
}

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Prepare the Test Environment Complete" -ForegroundColor Cyan
Write-Host $("=" * 80)
