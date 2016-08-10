@echo off
@echo Salt Windows Build Script
@echo ---------------------------------------------------------------------
@echo.

:: Make sure the script is run as Admin
@echo Administrative permissions required. Detecting permissions...
@echo ---------------------------------------------------------------------
net session >nul 2>&1
if %errorLevel%==0 (
    echo Success: Administrative permissions confirmed.
) else (
    echo Failure: This script must be run as Administrator
    goto eof
)
@echo.

:: Define Variables
@echo %0 :: Defining Variables...
@echo ---------------------------------------------------------------------
Set "PyDir=C:\Python27"
Set "CurDir=%~dp0"
Set PATH=%PATH%;C:\Python27;C:\Python27\Scripts
for /f "delims=" %%a in ('git rev-parse --show-toplevel') do @set "SrcDir=%%a"

:: Get the version from git if not passed
if [%1]==[] (
    for /f "delims=" %%a in ('git describe') do @set "Version=%%a"
) else (
    set "Version=%~1"
)
@echo.

:: Create Build Environment
@echo %0 :: Create the Build Environment...
@echo ---------------------------------------------------------------------
PowerShell.exe -ExecutionPolicy RemoteSigned -File "%CurDir%build_env.ps1" -Silent

if not %errorLevel%==0 (
    echo "%CurDir%build_env.ps1" returned errorlevel %errorLevel%. Aborting %0
    goto eof
)
@echo.

:: Install Current Version of salt
@echo %0 :: Install Current Version of salt...
@echo ---------------------------------------------------------------------
"%PyDir%\python.exe" "%SrcDir%\setup.py" --quiet install --force
@echo.

:: Build the Salt Package
@echo %0 :: Build the Salt Package...
@echo ---------------------------------------------------------------------
call "%CurDir%build_pkg.bat" "%Version%"
@echo.

:eof
@echo.
@echo =====================================================================
@echo End of %0
@echo =====================================================================
