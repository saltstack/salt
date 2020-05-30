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

:CheckPython27
if exist "\Python27" goto RemovePython27

goto CheckPython35

:RemovePython27
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
    echo %0 :: - 2.7.15 (32 bit)
    MsiExec.exe /X {16CD92A4-0152-4CB7-8FD6-9788D3363616} /QN
    echo %0 :: - 2.7.15 (64 bit)
    MsiExec.exe /X {16CD92A4-0152-4CB7-8FD6-9788D3363617} /QN

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

:CheckPython35
if exist "\Python35" goto RemovePython35

goto CheckPython37

:RemovePython35
    echo %0 :: Uninstalling Python 3 ...
    echo ---------------------------------------------------------------------
    :: 64 bit
    if exist "%LOCALAPPDATA%\Package Cache\{b94f45d6-8461-440c-aa4d-bf197b2c2499}" (
        echo %0 :: - 3.5.3 64bit
        "%LOCALAPPDATA%\Package Cache\{b94f45d6-8461-440c-aa4d-bf197b2c2499}\python-3.5.3-amd64.exe" /uninstall /quiet
    )
    if exist "%LOCALAPPDATA%\Package Cache\{5d57524f-af24-49a7-b90b-92138880481e}" (
        echo %0 :: - 3.5.4 64bit
        "%LOCALAPPDATA%\Package Cache\{5d57524f-af24-49a7-b90b-92138880481e}\python-3.5.4-amd64.exe" /uninstall /quiet
    )

    :: 32 bit
    if exist "%LOCALAPPDATA%\Package Cache\{a10037e1-4247-47c9-935b-c5ca049d0299}" (
        echo %0 :: - 3.5.3 32bit
        "%LOCALAPPDATA%\Package Cache\{a10037e1-4247-47c9-935b-c5ca049d0299}\python-3.5.3" /uninstall /quiet
    )
    if exist "%LOCALAPPDATA%\Package Cache\{06e841fa-ca3b-4886-a820-cd32c614b0c1}" (
        echo %0 :: - 3.5.4 32bit
        "%LOCALAPPDATA%\Package Cache\{06e841fa-ca3b-4886-a820-cd32c614b0c1}\python-3.5.4" /uninstall /quiet
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

:CheckPython37
if exist "\Python37" goto RemovePython37

goto eof

:RemovePython37
    echo %0 :: Uninstalling Python 3.7 ...
    echo ---------------------------------------------------------------------
    :: 64 bit
    if exist "%LOCALAPPDATA%\Package Cache\{8ae589dd-de2e-42cd-af56-102374115fee}" (
        echo %0 :: - 3.7.4 64bit
        "%LOCALAPPDATA%\Package Cache\{8ae589dd-de2e-42cd-af56-102374115fee}\python-3.7.4-amd64.exe" /uninstall /quiet
    )

    :: 32 bit
    if exist "%LOCALAPPDATA%\Package Cache\{b66087e3-469e-4725-8b9b-f0981244afea}" (
        echo %0 :: - 3.7.4 32bit
        "%LOCALAPPDATA%\Package Cache\{b66087e3-469e-4725-8b9b-f0981244afea}\python-3.7.4" /uninstall /quiet
    )
    :: Python Launcher, seems to be the same for 32 and 64 bit
    echo %0 :: - Python Launcher
    msiexec.exe /x {D722DA3A-92F5-454A-BD5D-A48C94D82300} /quiet /qn

    rem wipe the Python directory
    echo %0 :: Removing the C:\Python37 Directory ...
    echo ---------------------------------------------------------------------
    rd /s /q "C:\Python37"
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
