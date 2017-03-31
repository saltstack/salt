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

:: Uninstall Python 2.7.12
@echo %0 :: Uninstalling Python 2.7.12 ...
@echo ---------------------------------------------------------------------
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    :: 64 Bit
    MsiExec.exe /X {9DA28CE5-0AA5-429E-86D8-686ED898C666} /QN
) else (
    :: 32 Bit
    MsiExec.exe /X {9DA28CE5-0AA5-429E-86D8-686ED898C665} /QN
)
@echo.

:: Uninstall Python 3.5.3
@echo %0 :: Uninstalling Python 3.5.3 ...
@echo ---------------------------------------------------------------------
"%LOCALAPPDATA%\Package Cache\{b94f45d6-8461-440c-aa4d-bf197b2c2499}\python-3.5.3-amd64.exe" /uninstall


:: wipe the Python directory
if exist C:\Python27 (
    @echo %0 :: Removing the C:\Python27 Directory ...
    @echo ---------------------------------------------------------------------
    rd /s /q c:\Python27 || echo Failure: c:\Python27 still exists, please find out why and repeat.
)
if exist "C:\Program Files\Python35" (
    @echo %0 :: Removing the C:\Program Files\Python35 Directory ...
    @echo ---------------------------------------------------------------------
    rd /s /q "C:\Program Files\Python35" || echo Failure: c:\Python27 still exists, please find out why and repeat.
)
@echo.

@echo.
@echo =====================================================================
@echo End of %0
@echo =====================================================================
