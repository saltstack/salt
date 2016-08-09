@echo off
@echo Salt Windows Clean Script
@echo ---------------------------------------------------------------------
@echo.

:: Make sure the script is run as Admin
@ echo Administrative permissions required. Detecting permissions...
@echo ---------------------------------------------------------------------
net session >nul 2>&1
if %errorLevel%==0 (
    echo Success: Administrative permissions confirmed.
) else (
    echo Failure: This script must be run as Administrator
    goto eof
)
@echo.

:: Uninstall Python 2.7.12 64bit
@echo %0 :: Uninstalling Python 2.7.12 ...
@echo ---------------------------------------------------------------------
MsiExec.exe /X {9DA28CE5-0AA5-429E-86D8-686ED898C666} /QN
@echo.

:: wipe the Python directory
@echo %0 :: Removing the C:\Python27 Directory ...
@echo ---------------------------------------------------------------------
if exist C:\Python27 (
    rd /s /q c:\Python27 || echo Failure: c:\Python27 still exists, please find out why and repeat.
)
@echo.

@echo.
@echo =====================================================================
@echo End of %0
@echo =====================================================================
