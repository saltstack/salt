echo off
echo =====================================================================
echo Salt Windows Clean Script
echo =====================================================================
echo.

rem Make sure the script is run as Admin
echo Administrative permissions required. Detecting permissions...
echo ---------------------------------------------------------------------
net session >nul 2>&1
if %errorLevel%==0 (
    echo Success: Administrative permissions confirmed.
) else (
    echo Failure: This script must be run as Administrator
    goto eof
)
echo.

:CheckPython2
if exist "\Python27" goto RemovePython2

goto CheckPython3

:RemovePython2
    rem Uninstall Python 2.7
    echo %0 :: Uninstalling Python 2 ...
    echo ---------------------------------------------------------------------
    echo %0 :: - 2.7.12 (32 bit)
    MsiExec.exe /X {9DA28CE5-0AA5-429E-86D8-686ED898C665} /QN
    echo %0 :: - 2.7.12 (64 bit)
    MsiExec.exe /X {9DA28CE5-0AA5-429E-86D8-686ED898C666} /QN
    echo %0 :: - 2.7.13 (32 bit)
    MsiExec.exe /X {4A656C6C-D24A-473F-9747-3A8D00907A03} /QN
    echo %0 :: - 2.7.13 (64 bit)
    MsiExec.exe /X {4A656C6C-D24A-473F-9747-3A8D00907A04} /QN
    echo %0 :: - 2.7.14 (32 bit)
    MsiExec.exe /X {0398A685-FD8D-46B3-9816-C47319B0CF5E} /QN
    echo %0 :: - 2.7.14 (64 bit)
    MsiExec.exe /X {0398A685-FD8D-46B3-9816-C47319B0CF5F} /QN

    echo.

    rem Wipe the Python directory
    echo %0 :: Removing the C:\Python27 Directory ...
    echo ---------------------------------------------------------------------
    rd /s /q C:\Python27
    if %errorLevel%==0 (
        echo Successful
    ) else (
        echo Failed, please remove manually
    )

:CheckPython3
if exist "\Python35" goto RemovePython3

goto eof

:RemovePython3
    echo %0 :: Uninstalling Python 3 ...
    echo ---------------------------------------------------------------------
    :: 64 bit
    if exist "%LOCALAPPDATA%\Package Cache\{b94f45d6-8461-440c-aa4d-bf197b2c2499}" (
        echo %0 :: - 3.5.3 64bit
        "%LOCALAPPDATA%\Package Cache\{b94f45d6-8461-440c-aa4d-bf197b2c2499}\python-3.5.3-amd64.exe" /uninstall /quiet
    )

    :: 32 bit
    if exist "%LOCALAPPDATA%\Package Cache\{a10037e1-4247-47c9-935b-c5ca049d0299}" (
        echo %0 :: - 3.5.3 32bit
        "%LOCALAPPDATA%\Package Cache\{a10037e1-4247-47c9-935b-c5ca049d0299}\python-3.5.3" /uninstall /quiet
    )

    rem wipe the Python directory
    echo %0 :: Removing the C:\Python35 Directory ...
    echo ---------------------------------------------------------------------
    rd /s /q "C:\Python35"
    if %errorLevel%==0 (
        echo Successful
    ) else (
        echo Failed, please remove manually
    )

    goto eof

:eof
echo.
echo =====================================================================
echo End of %0
echo =====================================================================
