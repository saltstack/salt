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
@echo Defining Variables...
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
cmd /c powershell -ExecutionPolicy RemoteSigned -File "%CurDir%build_env.ps1" -Silent

:: Install Current Version of salt
cmd /c "%PyDir%\python.exe %SrcDir%\setup.py" install --force

:: Build the Salt Package
call "%CurDir%build_pkg.bat" "%Version%"

:eof
