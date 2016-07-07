@ echo off
@ echo Salt Windows Build Script
@ echo.

:: Make sure the script is run as Admin
@ echo Administrative permissions required. Detecting permissions...
net session >nul 2>&1
if %errorLevel%==0 (
    echo Success: Administrative permissions confirmed.
) else (
    echo Failure: This script must be run as Administrator
    goto eof
)

:: Define Variables
@echo %0 :: Defining Variables...
@echo ---------------------
Set "PyDir=C:\Python27"
Set "CurDir=%~dp0"
for /f "delims=" %%a in ('git rev-parse --show-toplevel') do @set "SrcDir=%%a"

if [%1]==[] (
    for /f "delims=" %%a in ('git describe') do @set "Version=%%a"
) else (
    set "Version=%~1"
)

:: Create Build Environment
PowerShell.exe -ExecutionPolicy RemoteSigned -File "%CurDir%build_env.ps1" -Silent

if not %errorLevel%==0 (
    echo "%CurDir%build_env.ps1" returned errorlevel %errorLevel%. Aborting %0
    goto eof
)

:: Install Current Version of salt
@echo  %0 :: Install Current Version of salt...
@echo ---------------------
"%PyDir%\python.exe" "%SrcDir%\setup.py" --quiet install --force

:: Build the Salt Package
@echo  %0 :: Build the Salt Package...
@echo ---------------------
call "%CurDir%build_pkg.bat" "%Version%"

:eof

@echo  End of %0
@echo ---------------------
