@echo off
@echo Salt Windows Build Script, which calls the other *.ps1 scripts.
@echo ---------------------------------------------------------------------
@echo.
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

:: If Version not defined, Get the version from Git
if "%Version%"=="" (
    for /f "delims=" %%a in ('git describe') do @set "Version=%%a"
)

@echo =====================================================================
@echo.

:: Define Variables
@echo %0 :: Defining Variables...
@echo ---------------------------------------------------------------------
Set "PyDir=C:\Python37"
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
call "%CurDir%build_pkg.bat" "%Version%"
@echo.

:eof
@echo.
@echo =====================================================================
@echo End of %0
@echo =====================================================================
