@echo off
@echo Salt Windows Build Package Script
@echo =====================================================================
@echo.

:: Get Passed Parameters
@echo %0 :: Get Passed Parameters...
@echo ---------------------------------------------------------------------
Set "Version="
Set "Python="
:: First Parameter
if not "%~1"=="" (
    echo.%1 | FIND /I "=" > nul && (
        :: Named Parameter
        set "%~1"
    ) || (
        :: Positional Parameter
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
if "%Version%"=="" (
    for /f "delims=" %%a in ('git describe') do @set "Version=%%a"
)

:: If Python not defined, Assume Python 2
if "%Python%"=="" (
    set Python=2
)

:: Verify valid Python value (2 or 3)
set "x="
for /f "delims=23" %%i in ("%Python%") do set x=%%i
if Defined x (
    echo Invalid Python Version specified. Must be 2 or 3. Passed %Python%
    goto eof
)
@echo.

:: Define Variables
@echo Defining Variables...
@echo ----------------------------------------------------------------------
if %Python%==2 (
    Set "PyDir=C:\Python27"
    Set "PyVerMajor=2"
    Set "PyVerMinor=7"
) else (
    Set "PyDir=C:\Program Files\Python35"
    Set "PyVerMajor=3"
    Set "PyVerMinor=5"
)

:: Verify the Python Installation
If not Exist "%PyDir%\python.exe" (
    @echo Expected version of Python not found: Python %PyVerMajor%.%PyVerMinor%"
    exit /b 1
)

Set "CurrDir=%cd%"
Set "BinDir=%cd%\buildenv\bin"
Set "InsDir=%cd%\installer"
Set "PreDir=%cd%\prereqs"

:: Find the NSIS Installer
If Exist "C:\Program Files\NSIS\" (
    Set "NSIS=C:\Program Files\NSIS\"
) Else (
    Set "NSIS=C:\Program Files (x86)\NSIS\"
)
If not Exist "%NSIS%NSIS.exe" (
    @echo "NSIS not found in %NSIS%"
    exit /b 1
)

:: Add NSIS to the Path
Set "PATH=%NSIS%;%PATH%"
@echo.

:: Check for existing bin directory and remove
If Exist "%BinDir%\" (
    @echo Removing %BinDir%
    @echo ----------------------------------------------------------------------
    rd /S /Q "%BinDir%"
)

:: Copy the contents of the Python Dir to bin
@echo Copying "%PyDir%" to bin...
@echo ----------------------------------------------------------------------
@echo xcopy /E /Q "%PyDir%" "%BinDir%\"
xcopy /E /Q "%PyDir%" "%BinDir%\"
@echo.

@echo Copying VCRedist to Prerequisites
@echo ----------------------------------------------------------------------
:: Make sure the "prereq" directory exists
If NOT Exist "%PreDir%" mkdir "%PreDir%"

:: Set the location of the vcredist to download
If %Python%==3 (
    Set Url64="http://repo.saltstack.com/windows/dependencies/64/vcredist_x64_2015.exe"
    Set Url32="http://repo.saltstack.com/windows/dependencies/32/vcredist_x86_2015.exe"

) Else (
    Set Url64="http://repo.saltstack.com/windows/dependencies/64/vcredist_x64_2008_mfc.exe"
    Set Url32="http://repo.saltstack.com/windows/dependencies/32/vcredist_x86_2008_mfc.exe"
)

:: Check for 64 bit by finding the Program Files (x86) directory
If Defined ProgramFiles(x86) (
    powershell -ExecutionPolicy RemoteSigned -File download_url_file.ps1 -url "%Url64%" -file "%PreDir%\vcredist.exe"
) Else (
    powershell -ExecutionPolicy RemoteSigned -File download_url_file.ps1 -url "%Url32%" -file "%PreDir%\vcredist.exe"
)
@echo.

:: Remove the fixed path in .exe files
@echo Removing fixed path from .exe files
@echo ----------------------------------------------------------------------
"%PyDir%\python" "%CurrDir%\portable.py" -f "%BinDir%\Scripts\easy_install.exe"
"%PyDir%\python" "%CurrDir%\portable.py" -f "%BinDir%\Scripts\easy_install-%PyVerMajor%.%PyVerMinor%.exe"
"%PyDir%\python" "%CurrDir%\portable.py" -f "%BinDir%\Scripts\pip.exe"
"%PyDir%\python" "%CurrDir%\portable.py" -f "%BinDir%\Scripts\pip%PyVerMajor%.%PyVerMinor%.exe"
"%PyDir%\python" "%CurrDir%\portable.py" -f "%BinDir%\Scripts\pip%PyVerMajor%.exe"
@echo.

@echo Cleaning up unused files and directories...
@echo ----------------------------------------------------------------------
:: Remove all Compiled Python files (.pyc)
del /S /Q "%BinDir%\*.pyc" 1>nul
:: Remove all Compiled HTML Help (.chm)
del /S /Q "%BinDir%\*.chm" 1>nul
:: Remove all empty text files (they are placeholders for git)
del /S /Q "%BinDir%\..\empty.*" 1>nul

:: Delete Unused Docs and Modules
If Exist "%BinDir%\Doc"           rd /S /Q "%BinDir%\Doc"
If Exist "%BinDir%\share"         rd /S /Q "%BinDir%\share"
If Exist "%BinDir%\tcl"           rd /S /Q "%BinDir%\tcl"
If Exist "%BinDir%\Lib\idlelib"   rd /S /Q "%BinDir%\Lib\idlelib"
If Exist "%BinDir%\Lib\lib-tk"    rd /S /Q "%BinDir%\Lib\lib-tk"
If Exist "%BinDir%\Lib\test"      rd /S /Q "%BinDir%\Lib\test"
If Exist "%BinDir%\Lib\unit-test" rd /S /Q "%BinDir%\Lib\unit-test"

:: Delete Unused .dll files
If Exist "%BinDir%\DLLs\tcl85.dll"    del /Q "%BinDir%\DLLs\tcl85.dll"    1>nul
If Exist "%BinDir%\DLLs\tclpip85.dll" del /Q "%BinDir%\DLLs\tclpip85.dll" 1>nul
If Exist "%BinDir%\DLLs\tk85.dll"     del /Q "%BinDir%\DLLs\tk85.dll"     1>nul

:: Delete Unused .lib files
If Exist "%BinDir%\libs\_tkinter.lib" del /Q "%BinDir%\libs\_tkinter.lib" 1>nul

:: Delete .txt files
If Exist "%BinDir%\NEWS.txt"   del /Q "%BinDir%\NEWS.txt"   1>nul
If Exist "%BinDir%\README.txt" del /Q "%BinDir%\README.txt" 1>nul

:: Delete Non-Windows Modules
If Exist "%BinDir%\Lib\site-packages\salt\modules\acme.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\acme.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\alternatives.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\alternatives.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\apf.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\apf.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\aptpkg.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\aptpkg.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\at.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\at.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\bcache.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\bcache.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\blockdev.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\blockdev.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\bluez.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\bluez.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\bridge.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\bridge.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\bsd_shadow.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\bsd_shadow.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\btrfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\btrfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\ceph.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\ceph.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\container_resource.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\container_resource.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\cron.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\cron.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\csf.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\csf.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\daemontools.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\daemontools.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\deb*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\deb*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\devmap.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\devmap.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\dpkg.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\dpkg.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\ebuild.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\ebuild.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\eix.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\eix.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\eselect.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\eselect.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\ethtool.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\ethtool.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\extfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\extfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\firewalld.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\firewalld.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\freebsd*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\freebsd*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\genesis.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\genesis.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\gentoo*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\gentoo*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\glusterfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\glusterfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\gnomedesktop.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\gnomedesktop.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\groupadd.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\groupadd.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\grub_legacy.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\grub_legacy.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\guestfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\guestfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\htpasswd.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\htpasswd.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\ilo.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\ilo.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\img.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\img.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\incron.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\incron.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\inspector.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\inspector.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\ipset.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\ipset.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\iptables.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\iptables.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\iwtools.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\iwtools.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\k8s.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\k8s.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\kapacitor.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\kapacitor.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\keyboard.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\keyboard.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\keystone.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\keystone.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\kmod.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\kmod.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\layman.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\layman.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\linux*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\linux*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\localemod.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\localemod.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\locate.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\locate.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\logadm.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\logadm.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\logrotate.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\logrotate.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\lvs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\lvs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\lxc.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\lxc.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\mac*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\mac*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\makeconf.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\makeconf.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\mdadm.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\mdadm.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\mdata.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\mdata.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\monit.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\monit.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\moosefs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\moosefs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\mount.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\mount.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\napalm*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\napalm*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\netbsd*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\netbsd*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\netscaler.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\netscaler.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\neutron.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\neutron.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\nfs3.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\nfs3.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\nftables.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\nftables.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\nova.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\nova.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\nspawn.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\nspawn.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\openbsd*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\openbsd*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\openstack_mng.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\openstack_mng.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\openvswitch.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\openvswitch.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\opkg.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\opkg.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\pacman.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\pacman.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\parallels.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\parallels.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\parted.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\parted.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\pcs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\pcs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\pkgin.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\pkgin.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\pkgng.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\pkgng.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\pkgutil.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\pkgutil.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\portage_config.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\portage_config.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\postfix.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\postfix.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\poudriere.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\poudriere.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\powerpath.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\powerpath.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\pw_*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\pw_*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\qemu_ndb.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\qemu_ndb.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\quota.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\quota.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\redismod.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\redismod.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\restartcheck.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\restartcheck.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\rh_*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\rh_*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\riak.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\riak.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\rpm*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\rpm*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\runit.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\runit.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\s6.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\s6.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\scsi.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\scsi.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\seed.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\seed.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\sensors.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\sensors.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\service.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\service.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\shadow.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\shadow.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\smartos*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\smartos*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\smf.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\smf.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\snapper.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\snapper.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\solaris*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\solaris*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\solr.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\solr.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\ssh*"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\ssh*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\supervisord.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\supervisord.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\sysbench.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\sysbench.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\sysfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\sysfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\sysrc.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\sysrc.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\system.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\system.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\test_virtual.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\test_virtual.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\timezone.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\timezone.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\trafficserver.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\trafficserver.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\tuned.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\tuned.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\udev.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\udev.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\upstart.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\upstart.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\useradd.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\useradd.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\uswgi.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\uswgi.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\varnish.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\varnish.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\vbox_guest.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\vbox_guest.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\vboxmanage.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\vboxmanage.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\virt.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\virt.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\xapi.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\xapi.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\xbpspkg.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\xbpspkg.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\xfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\xfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\yumpkg.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\yum.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\zabbix.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\zabbix.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\zfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\zfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\znc.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\znc.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\zpool.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\zpool.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\modules\zypper.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\modules\zypper.*" 1>nul

:: Delete Non-Windows States
If Exist "%BinDir%\Lib\site-packages\salt\states\acme.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\acme.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\alternatives.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\alternatives.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\aptpkg.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\aptpkg.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\at.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\at.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\blockdev.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\blockdev.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\ceph.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\ceph.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\cron.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\cron.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\csf.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\csf.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\debconfmod.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\debconfmod.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\eselect.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\eselect.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\ethtool.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\ethtool.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\firewalld.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\firewalld.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\glusterfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\glusterfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\gnomedesktop.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\gnomedesktop.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\htpasswd.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\htpasswd.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\incron.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\incron.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\ipset.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\ipset.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\iptables.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\iptables.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\k8s.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\k8s.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\kapacitor.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\kapacitor.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\keyboard.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\keyboard.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\keystone.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\keystone.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\kmod.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\kmod.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\layman.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\layman.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\linux*"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\linux*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\lxc.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\lxc.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\mac_*"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\mac_*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\makeconf.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\makeconf.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\mdadm.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\mdadm.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\monit.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\monit.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\mount.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\mount.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\nftables.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\nftables.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\pcs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\pcs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\pkgng.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\pkgng.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\portage_config.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\portage_config.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\powerpath.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\powerpath.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\quota.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\quota.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\redismod.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\redismod.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\smartos.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\smartos.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\snapper.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\snapper.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\ssh*"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\ssh*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\supervisord.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\supervisord.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\sysrc.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\sysrc.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\trafficserver.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\trafficserver.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\tuned.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\tuned.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\vbox_guest.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\vbox_guest.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\virt.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\virt.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\zabbix*"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\zabbix*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\zfs.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\zfs.*" 1>nul
If Exist "%BinDir%\Lib\site-packages\salt\states\zpool.py"^
    del /Q "%BinDir%\Lib\site-packages\salt\states\zpool.*" 1>nul

:: Remove Unneeded Components
If Exist "%BinDir%\Lib\site-packages\salt\cloud"^
    rd /S /Q "%BinDir%\Lib\site-packages\salt\cloud" 1>nul
If Exist "%BinDir%\Scripts\salt-key*"^
    del /Q "%BinDir%\Scripts\salt-key*" 1>nul
If Exist "%BinDir%\Scripts\salt-master*"^
    del /Q "%BinDir%\Scripts\salt-master*" 1>nul
If Exist "%BinDir%\Scripts\salt-run*"^
    del /Q "%BinDir%\Scripts\salt-run*" 1>nul
If Exist "%BinDir%\Scripts\salt-unity*"^
    del /Q "%BinDir%\Scripts\salt-unity*" 1>nul

@echo.

@echo Building the installer...
@echo ----------------------------------------------------------------------
makensis.exe /DSaltVersion=%Version% /DPythonVersion=%Python% "%InsDir%\Salt-Minion-Setup.nsi"
@echo.

@echo.
@echo ======================================================================
@echo Script completed...
@echo ======================================================================
@echo Installation file can be found in the following directory:
@echo %InsDir%

:done
if [%Version%] == [] pause
