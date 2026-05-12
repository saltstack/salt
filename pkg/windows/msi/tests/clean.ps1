# Clean up the test environment

#-------------------------------------------------------------------------------
# Script Variables
#-------------------------------------------------------------------------------

$PROJECT_DIR  = $(git rev-parse --show-toplevel)
$SCRIPT_DIR   = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$BUILD_DIR    = "$PROJECT_DIR\pkg\windows\build"
$BUILDENV_DIR = "$PROJECT_DIR\pkg\windows\buildenv"
$TESTS_DIR    = "$SCRIPT_DIR\config_tests"

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
Write-Host "Clean the Test Environment" -ForegroundColor Cyan
Write-Host $("-" * 80)

#-------------------------------------------------------------------------------
# Delete Files
#-------------------------------------------------------------------------------

$delete_files = "*.bat",
                "*.install.log",
                "*.output",
                "*.uninstall.log",
                "*.un~"
$delete_files | ForEach-Object {
    if ( Test-Path -Path "$TESTS_DIR\$_" ) {
        Write-Host "Deleting $_`: " -NoNewline
        Remove-Item -Path "$TESTS_DIR\$_" -Force -Recurse -ErrorAction SilentlyContinue
        if (!(Test-Path -Path "$TESTS_DIR\$_")) {
            Write-Result "Success"
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

#-------------------------------------------------------------------------------
# Delete Build Directories
#-------------------------------------------------------------------------------

$delete_dirs = $BUILD_DIR,
               $BUILDENV_DIR
$delete_dirs | ForEach-Object {
    if ( Test-Path -Path "$_" ) {
        Write-Host "Deleting $_`: " -NoNewline
        Remove-Item -Path "$_" -Force -Recurse
        if ( ! (Test-Path -Path "$_") ) {
            Write-Result "Success"
        } else {
            Write-Result "Failed" -ForegroundColor Red
            exit 1
        }
    }
}

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------

Write-Host $("-" * 80)
Write-Host "Prepare the Test Environment Complete" -ForegroundColor Cyan
Write-Host $("=" * 80)
