@ echo off
:: Define Variables
@ echo Defining Variables...
Set "CurrDir=%cd%"
Set "BinDir=%cd%\buildenv\bin"
Set "InsDir=%cd%\installer"
Set "PyDir=C:\Python27"

:: Find the NSIS Installer
If Exist "C:\Program Files\NSIS\" (
    Set NSIS="C:\Program Files\NSIS\"
) Else (
    Set NSIS="C:\Program Files (x86)\NSIS\"
)
Set "PATH=%NSIS%;%PATH%"

@ echo Copying C:\Python27 to bin...
:: Check for existing bin directory and remove
If Exist "%BinDir%\" rd "%BinDir%" /S /Q

:: Copy the Python27 directory to bin
xcopy /S /E %PyDir% %CurrDir%\buildenv\bin\

@ echo Cleaning up unused files and directories...
:: Remove all Compiled Python files (.pyc)
del /S /Q %BinDir%\*.pyc

:: Delete Unused Docs and Modules
rd /S /Q %BinDir%\Doc
rd /S /Q %BinDir%\share
rd /S /Q %BinDir%\tcl
rd /S /Q %BinDir%\Lib\idlelib
rd /S /Q %BinDir%\Lib\lib-tk
rd /S /Q %BinDir%\Lib\test
rd /S /Q %BinDir%\Lib\unit-test

:: Delete Unused .dll files
del /S /Q %BinDir%\DLLs\tcl85.dll
del /S /Q %BinDir%\DLLs\tclpip85.dll
del /S /Q %BinDir%\DLLs\tk85.dll

:: Delete .txt files
del /q %BinDir%\NEWS.txt
del /q %BinDir%\README.txt

@ echo Building the installer...
makensis.exe "%InsDir%\Salt-Minion-Setup.nsi

@ echo.
@ echo Script completed...
@ echo Installation file can be found in the following directory:
@ echo %InsDir%
pause
cls
