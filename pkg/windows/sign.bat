:: ############################################################################
::
::              FILE: sign.bat
::
::       DESCRIPTION: Signing and Hashing script for Salt builds on Windows.
::                    Requires an official Code Signing Certificate and drivers
::                    installed to sign the files. Generates hashes in MD5 and
::                    SHA256 in a file of the same name with a `.md5` or
::                    `.sha256` extension.
::
::              NOTE: This script is used internally by SaltStack to sign and
::                    hash Windows Installer builds and uses resources not
::                    available to the community, such as SaltStack's Code
::                    Signing Certificate. It is placed here for version
::                    control.
::
::         COPYRIGHT: (c) 2012-2018 by the SaltStack Team
::
::           LICENSE: Apache 2.0
::      ORGANIZATION: VMware, Inc (saltstack.com)
::           CREATED: 2017
::
:: ############################################################################
::
:: USAGE: The script must be located in a directory that has the installer
::        files in a subfolder named with the major version, ie: `2018.3`.
::        Insert the key fob that contains the code signing certificate. Run
::        the script passing the full version: `.\sign.bat 2018.3.1`.
::
::        The script will sign the installers and generate the corresponding
::        hash files. These can then be uploaded to the salt repo.
::
::        The files must be in the following format:
::        <Series>\Salt-Minion-<Version>-<Python Version>-<System Architecture>-Setup.exe
::        So, for a Salt Minion installer for 2018.3.1 on AMD64 for Python 3
::        file would be placed in a subdirectory named `2018.3` and the file
::        would be named: `Salt-Minion-2018.3.1-Py3-AMD64-Setup.exe`. This
::        is how the file is created by the NSI Script anyway.
::
:: ############################################################################
@ echo off
if [%1]==[] (
    echo You must pass a version
    goto quit
) else (
    set "Version=%~1"
)

for /F "tokens=1,2 delims=." %%a in ("%Version%") do (set Series=%%a.%%b)

:: See if the Series Directory exists (uses new versioning)
if not exist .\%Series%\ (
    echo - Series %Series% was not found, trying new naming convention
    for /F "tokens=1,2 delims=." %%a in ("%Version%") do (set Series=%%a)
)
if not exist .\%Series%\ (
    echo - Series %Series% is not valid
    exit 1
)

:: If it ends in a '.' trim it
if "%Series:~-1%"=="." (
    set Series=%Series:~0,-1%
)

:: Sign Installer Files
echo ===========================================================================
echo Signing...
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
signtool.exe sign /a /t http://timestamp.digicert.com ^
                     "%Series%\Salt-Minion-%Version%-AMD64-Setup.exe" ^
                     "%Series%\Salt-Minion-%Version%-x86-Setup.exe" ^
                     "%Series%\Salt-%Version%-AMD64-Setup.exe" ^
                     "%Series%\Salt-%Version%-x86-Setup.exe" ^
                     "%Series%\Salt-%Version%-Py2-AMD64-Setup.exe" ^
                     "%Series%\Salt-%Version%-Py2-x86-Setup.exe" ^
                     "%Series%\Salt-%Version%-Py3-AMD64-Setup.exe" ^
                     "%Series%\Salt-%Version%-Py3-x86-Setup.exe" ^
                     "%Series%\Salt-Minion-%Version%-Py2-AMD64-Setup.exe" ^
                     "%Series%\Salt-Minion-%Version%-Py2-x86-Setup.exe" ^
                     "%Series%\Salt-Minion-%Version%-Py3-AMD64-Setup.exe" ^
                     "%Series%\Salt-Minion-%Version%-Py3-x86-Setup.exe"

echo %ERRORLEVEL%
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo Signing Complete
echo ===========================================================================

:: Create Hash files
echo ===========================================================================
echo Creating Hashes...
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
set "file_name=Salt-Minion-%Version%-AMD64-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)


set "file_name=Salt-Minion-%Version%-x86-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-%Version%-AMD64-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-%Version%-x86-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-%Version%-Py2-AMD64-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-%Version%-Py2-x86-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-%Version%-Py3-AMD64-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-%Version%-Py3-x86-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-Minion-%Version%-Py2-AMD64-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-Minion-%Version%-Py2-x86-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)
	
set "file_name=Salt-Minion-%Version%-Py3-AMD64-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

set "file_name=Salt-Minion-%Version%-Py3-x86-Setup.exe"
set "file=.\%Series%\%file_name%"
if exist "%file%" (
    echo - %file_name%
    powershell -c "$hash = (Get-FileHash -Algorithm MD5 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.md5\"" -NoNewLine
    powershell -c "$hash = (Get-FileHash -Algorithm SHA256 \"%file%\").Hash; Out-File -InputObject $hash\" %file_name%\" -FilePath \"%file%.sha256\"" -NoNewLine)

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo Hashing Complete
echo ===========================================================================

:quit
