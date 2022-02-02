@echo off
@echo Salt Windows Build Script, which calls the other *.ps1 scripts.
@echo ---------------------------------------------------------------------
@echo.
:: This script builds salt on any machine. It uses the following scripts:
:: - build_env.ps1: Sets up a Python environment will all dependencies salt will
::                  will require
:: - build_pkg.bat: Bundles the contents of the Python directory into a
::                  nullsoft installer binary

:: The script first calls the `build_env.ps1` script to set up a python
:: environment. Then it installs Salt into that python environment using Salt's
:: `setup.py install` command. Finally, it runs the `build_pkg.bat` to create
:: a NullSoft installer in the `installer` directory (pkg\windows\installer)

:: This script accepts two parameters.
::   Version: The version of Salt being built. If not passed, the version will
::            determined using `git describe`. The leading `v` will be removed
::   Python: The version of Python to build Salt on (Default is 3)

:: These parameters can be passed positionally or as named parameters. Named
:: parameters must be wrapped in quotes.

:: Examples:
::   # To build Salt 3000.3 on Python 3
::   build.bat 3000.3
::   build.bat 3000.3 3

::   # Using named parameters
::   build.bat "Version=3000.3"
::   build.bat "Version=3000.3" "Python=3"

::  # Using a mix
::   build.bat 3000.3 "Python=3"

:: To activate caching, set environment variables
::   SALTREPO_LOCAL_CACHE  for resources from saltstack.com/...
::   SALT_REQ_LOCAL_CACHE  for pip resources specified in req.txt
::   SALT_PIP_LOCAL_CACHE  for pip resources specified in req_pip.txt

:: Make sure the script is run as Admin
@echo Administrative permissions required. Detecting permissions...
@echo ---------------------------------------------------------------------
net session >nul 2>&1
if %errorLevel%==0 (
    echo ...Success: Administrative permissions confirmed.
) else (
    echo ...Failure: This script must be run as Administrator
    goto eof
)
@echo =====================================================================
@echo.

@echo Git required. Detecting git...
@echo ---------------------------------------------------------------------
where git >nul 2>&1
if %errorLevel%==0 (
    echo ...Success: Git found.
) else (
    echo ...Failure: This script needs to call git
    goto eof
)
@echo =====================================================================
@echo.

:: Get Passed Parameters
@echo %0 :: Get Passed Parameters...
@echo ---------------------------------------------------------------------

set "Version="
set "Python="
:: First Parameter
if not "%~1"=="" (
    echo.%1 | FIND /I "=" > nul && (
        :: Named Parameter
        echo Named Parameter
        set "%~1"
    ) || (
        :: Positional Parameter
        echo Positional Parameter
        set "Version=%~1"
    )
)

:: Second Parameter
if not "%~2"=="" (
    echo.%2 | FIND /I "=" > nul && (
        :: Named Parameter
        set "%~2"
    ) || (
        :: Positional Parameter
        set "Python=%~2"
    )
)

:: If Version not defined, Get the version from Git
set git=0
if "%Version%"=="" (
    echo Getting version from git
    for /f "delims=" %%a in ('git describe') do @set "Version=%%a"
    set git=1
)
:: Strip off the leading `v` when getting version from git describe
if %git%==1 set Version=%Version:~1%

:: If Python not defined, Assume Python 3
if "%Python%"=="" (
    set Python=3
)

:: Verify valid Python value (3)
:: We may need to add Python 4 in the future (delims=34)
set "x="
for /f "delims=3" %%i in ("%Python%") do set x=%%i
if Defined x (
    echo Invalid Python Version specified. Must be 3. Passed %Python%
    goto eof
)

@echo =====================================================================
@echo.

:: Define Variables
@echo %0 :: Defining Variables...
@echo ---------------------------------------------------------------------
if "%PyDir%"=="" (Set "PyDir=C:\Python38")
if "%PyVerMajor%"=="" (Set "PyVerMajor=3")
if "%PyDirMinor%"=="" (Set "PyVerMinor=8")
Set "PATH=%PATH%;%PyDir%;%PyDir%\Scripts"

Set "CurDir=%~dp0"
for /f "delims=" %%a in ('git rev-parse --show-toplevel') do @set "SrcDir=%%a"

@echo =====================================================================
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

:: Remove build and dist directories
@echo %0 :: Remove build and dist directories...
@echo ---------------------------------------------------------------------
"%PyDir%\python.exe" "%SrcDir%\setup.py" clean --all
if not %errorLevel%==0 (
    goto eof
)
If Exist "%SrcDir%\dist" (
    @echo removing %SrcDir%\dist
    rd /S /Q "%SrcDir%\dist"
)
@echo.

:: Install Current Version of salt
@echo %0 :: Install Current Version of salt...
@echo ---------------------------------------------------------------------
"%PyDir%\python.exe" "%SrcDir%\setup.py" --quiet install --force
if not %errorLevel%==0 (
    goto eof
)
@echo.

:: Build the Salt Package
@echo %0 :: Build the Salt Package...
@echo ---------------------------------------------------------------------
call "%CurDir%build_pkg.bat" "%Version%" "%Python%"
@echo.

:eof
@echo.
@echo =====================================================================
@echo End of %0
@echo =====================================================================
