#==============================================================================
# You may need to change the execution policy in order to run this script
# Run the following in powershell:
#
# Set-ExecutionPolicy RemoteSigned
#
#==============================================================================
#
#          FILE: dev_env.ps1
#
#   DESCRIPTION: Development Environment Installation for Windows
#
#          BUGS: https://github.com/saltstack/salt-windows-bootstrap/issues
#
#     COPYRIGHT: (c) 2012-2017 by the SaltStack Team, see AUTHORS.rst for more
#                details.
#
#       LICENSE: Apache 2.0
#  ORGANIZATION: SaltStack (saltstack.org)
#       CREATED: 03/10/2017
#==============================================================================

# Load parameters
param(
    [switch]$Silent,
    [switch]$NoPipDependencies
)

#==============================================================================
# Get the Directory of actual script
#==============================================================================
$script_path = dir "$($myInvocation.MyCommand.Definition)"
$script_path = $script_path.DirectoryName

#==============================================================================
# Get the name of actual script
#==============================================================================
$script_name = $MyInvocation.MyCommand.Name

Write-Output "================================================================="
Write-Output ""
Write-Output "               Development Environment Installation"
Write-Output ""
Write-Output "               - Installs All Salt Dependencies"
Write-Output "               - Detects 32/64 bit Architectures"
Write-Output ""
Write-Output "               To run silently add -Silent"
Write-Output "               eg: ${script_name} -Silent"
Write-Output ""
Write-Output "               To run skip installing pip dependencies add -NoPipDependencies"
Write-Output "               eg: ${script_name} -NoPipDependencies"
Write-Output ""
Write-Output "================================================================="
Write-Output ""

#==============================================================================
# Import Modules
#==============================================================================
Import-Module $script_path\Modules\download-module.psm1
Import-Module $script_path\Modules\get-settings.psm1
Import-Module $script_path\Modules\uac-module.psm1
Import-Module $script_path\Modules\zip-module.psm1
Import-Module $script_path\Modules\start-process-and-test-exitcode.psm1
#==============================================================================
# Check for Elevated Privileges
#==============================================================================
If (!(Get-IsAdministrator)) {
    If (Get-IsUacEnabled) {
        # We are not running "as Administrator" - so relaunch as administrator
        # Create a new process object that starts PowerShell
        $newProcess = new-object System.Diagnostics.ProcessStartInfo "PowerShell";

        # Specify the current script path and name as a parameter
        $newProcess.Arguments = $myInvocation.MyCommand.Definition

        # Specify the current working directory
        $newProcess.WorkingDirectory = "$script_path"

        # Indicate that the process should be elevated
        $newProcess.Verb = "runas";

        # Start the new process
        [System.Diagnostics.Process]::Start($newProcess);

        # Exit from the current, unelevated, process
        Exit
    } Else {
        Throw "You must be administrator to run this script"
    }
}

#------------------------------------------------------------------------------
# Load Settings
#------------------------------------------------------------------------------
$ini = Get-Settings

#------------------------------------------------------------------------------
# Create Directories
#------------------------------------------------------------------------------
$p = New-Item $ini['Settings']['DownloadDir'] -ItemType Directory -Force
$p = New-Item "$($ini['Settings']['DownloadDir'])\64" -ItemType Directory -Force
$p = New-Item "$($ini['Settings']['DownloadDir'])\32" -ItemType Directory -Force
$p = New-Item $ini['Settings']['SaltDir'] -ItemType Directory -Force

#------------------------------------------------------------------------------
# Determine Architecture (32 or 64 bit) and assign variables
#------------------------------------------------------------------------------
If ([System.IntPtr]::Size -ne 4) {
    Write-Output "Detected 64bit Architecture..."

    $bitDLLs     = "64bitDLLs"
    $bitPaths    = "64bitPaths"
    $bitPrograms = "64bitPrograms"
    $bitFolder   = "64"
} Else {
    Write-Output "Detected 32bit Architecture"
    $bitDLLs     = "32bitDLLs"
    $bitPaths    = "32bitPaths"
    $bitPrograms = "32bitPrograms"
    $bitFolder   = "32"
}

#------------------------------------------------------------------------------
# Check for installation of NSIS
#------------------------------------------------------------------------------
Write-Output " - Checking for NSIS installation . . ."
If (Test-Path "$($ini[$bitPaths]['NSISDir'])\NSIS.exe") {
    # Found NSIS, do nothing
    Write-Output " - NSIS Found . . ."
} Else {
    # NSIS not found, install
    Write-Output " - NSIS Not Found . . ."
    Write-Output " - Downloading $($ini['Prerequisites']['NSIS']) . . ."
    $file = "$($ini['Prerequisites']['NSIS'])"
    $url  = "$($ini['Settings']['SaltRepo'])/$file"
    $file = "$($ini['Settings']['DownloadDir'])\$file"
    DownloadFileWithProgress $url $file

    # Install NSIS
    Write-Output " - Installing $($ini['Prerequisites']['NSIS']) . . ."
    $file = "$($ini['Settings']['DownloadDir'])\$($ini['Prerequisites']['NSIS'])"
    $p    = Start-Process $file -ArgumentList '/S' -Wait -NoNewWindow -PassThru
}

#------------------------------------------------------------------------------
# Check for installation of NSIS NxS Unzip Plug-in
#------------------------------------------------------------------------------
Write-Output " - Checking for NSIS NxS Unzip (ansi) Plug-in installation . . ."
If (Test-Path "$( $ini[$bitPaths]['NSISPluginsDirA'] )\nsisunz.dll") {
    # Found NSIS NxS Unzip Plug-in, do nothing
    Write-Output " - NSIS NxS Unzip Plugin (ansi) Found . . ."
} Else
{
    # NSIS NxS Unzip Plug-in (ansi) not found, install
    Write-Output " - NSIS NxS Unzip Plugin (ansi) Not Found . . ."
    # Ansi Plugin
    Write-Output " - Downloading $( $ini['Prerequisites']['NSISPluginUnzipA'] ) . . ."
    $file = "$( $ini['Prerequisites']['NSISPluginUnzipA'] )"
    $url  = "$( $ini['Settings']['SaltRepo'] )/$file"
    $file = "$( $ini['Settings']['DownloadDir'] )\$file"
    DownloadFileWithProgress $url $file

    # Extract Ansi Zip file
    Write-Output " - Extracting . . ."
    Expand-ZipFile $file $ini['Settings']['DownloadDir']

    # Copy dll to plugins directory
    Write-Output " - Copying dll to plugins directory . . ."
    Move-Item "$( $ini['Settings']['DownloadDir'] )\nsisunz\Release\nsisunz.dll" "$( $ini[$bitPaths]['NSISPluginsDirA'] )\nsisunz.dll" -Force

    # Remove temp files
    Remove-Item "$( $ini['Settings']['DownloadDir'] )\nsisunz" -Force -Recurse
    Remove-Item "$file" -Force
}

Write-Output " - Checking for NSIS NxS Unzip (unicode) Plug-in installation . . ."
If (Test-Path "$( $ini[$bitPaths]['NSISPluginsDirU'] )\nsisunz.dll") {
    # Found NSIS NxS Unzip Plug-in (unicode), do nothing
    Write-Output " - NSIS NxS Unzip Plugin (unicode) Found . . ."
} Else {
    # Unicode Plugin
    Write-Output " - Downloading $( $ini['Prerequisites']['NSISPluginUnzipU'] ) . . ."
    $file = "$( $ini['Prerequisites']['NSISPluginUnzipU'] )"
    $url  = "$( $ini['Settings']['SaltRepo'] )/$file"
    $file = "$( $ini['Settings']['DownloadDir'] )\$file"
    DownloadFileWithProgress $url $file

    # Extract Unicode Zip file
    Write-Output " - Extracting . . ."
    Expand-ZipFile $file $ini['Settings']['DownloadDir']

    # Copy dll to plugins directory
    Write-Output " - Copying dll to plugins directory . . ."
    Move-Item "$( $ini['Settings']['DownloadDir'] )\NSISunzU\Plugin unicode\nsisunz.dll" "$( $ini[$bitPaths]['NSISPluginsDirU'] )\nsisunz.dll" -Force

    # Remove temp files
    Remove-Item "$( $ini['Settings']['DownloadDir'] )\NSISunzU" -Force -Recurse
    Remove-Item "$file" -Force
}

#------------------------------------------------------------------------------
# Check for installation of EnVar Plugin for NSIS
#------------------------------------------------------------------------------
Write-Output " - Checking for EnVar Plugin of NSIS installation  . . ."
If ( (Test-Path "$($ini[$bitPaths]['NSISPluginsDirA'])\EnVar.dll") -and (Test-Path "$($ini[$bitPaths]['NSISPluginsDirU'])\EnVar.dll") ) {
    # Found EnVar Plugin for NSIS, do nothing
    Write-Output " - EnVar Plugin for NSIS Found . . ."
} Else {
    # EnVar Plugin for NSIS not found, install
    Write-Output " - EnVar Plugin for NSIS Not Found . . ."
    Write-Output " - Downloading $($ini['Prerequisites']['NSISPluginEnVar']) . . ."
    $file = "$($ini['Prerequisites']['NSISPluginEnVar'])"
    $url  = "$($ini['Settings']['SaltRepo'])/$file"
    $file = "$($ini['Settings']['DownloadDir'])\$file"
    DownloadFileWithProgress $url $file

    # Extract Zip File
    Write-Output " - Extracting . . ."
    Expand-ZipFile $file "$($ini['Settings']['DownloadDir'])\nsisenvar"

    # Copy dlls to plugins directory (both ANSI and Unicode)
    Write-Output " - Copying dlls to plugins directory . . ."
    Move-Item "$( $ini['Settings']['DownloadDir'] )\nsisenvar\Plugins\x86-ansi\EnVar.dll" "$( $ini[$bitPaths]['NSISPluginsDirA'] )\EnVar.dll" -Force
    Move-Item "$( $ini['Settings']['DownloadDir'] )\nsisenvar\Plugins\x86-unicode\EnVar.dll" "$( $ini[$bitPaths]['NSISPluginsDirU'] )\EnVar.dll" -Force

    # Remove temp files
    Remove-Item "$( $ini['Settings']['DownloadDir'] )\nsisenvar" -Force -Recurse
    Remove-Item "$file" -Force

}

#------------------------------------------------------------------------------
# Check for installation of Microsoft Visual C++ Build Tools
#------------------------------------------------------------------------------
Write-Output " - Checking for Microsoft Visual C++ Build Tools installation . . ."
If (Test-Path "$($ini[$bitPaths]['VCppBuildToolsDir'])\vcbuildtools.bat") {
    # Found Microsoft Visual C++ Build Tools, do nothing
    Write-Output " - Microsoft Visual C++ Build Tools Found . . ."
} Else {
    # Microsoft Visual C++ Build Tools not found, install
    Write-Output " - Microsoft Visual C++ Build Tools Not Found . . ."
    Write-Output " - Downloading $($ini['Prerequisites']['VCppBuildTools']) . . ."
    $file = "$($ini['Prerequisites']['VCppBuildTools'])"
    $url  = "$($ini['Settings']['SaltRepo'])/$file"
    $file = "$($ini['Settings']['DownloadDir'])\$file"
    DownloadFileWithProgress $url $file

    # Install Microsoft Visual C++ Build Tools
    Write-Output " - Installing $($ini['Prerequisites']['VCppBuildTools']) . . ."
    $file = "$($ini['Settings']['DownloadDir'])\$($ini['Prerequisites']['VCppBuildTools'])"
    $p    = Start-Process $file -ArgumentList '/Quiet' -Wait -NoNewWindow -PassThru
}

#------------------------------------------------------------------------------
# Install Python
#------------------------------------------------------------------------------
Write-Output " - Checking for Python 3 installation . . ."
If (Test-Path "$($ini['Settings']['Python3Dir'])\python.exe") {
    # Found Python 3, do nothing
    Write-Output " - Python 3 Found . . ."
} Else {
    Write-Output " - Downloading $($ini[$bitPrograms]['Python3']) . . ."
    $file = "$($ini[$bitPrograms]['Python3'])"
    $url  = "$($ini['Settings']['SaltRepo'])/$bitFolder/$file"
    $file = "$($ini['Settings']['DownloadDir'])\$bitFolder\$file"
    DownloadFileWithProgress $url $file

    Write-Output " - $script_name :: Installing $($ini[$bitPrograms]['Python3']) . . ."
    $p    = Start-Process $file -ArgumentList "/Quiet InstallAllUsers=1 TargetDir=`"$($ini['Settings']['Python3Dir'])`" Include_doc=0 Include_tcltk=0 Include_test=0 Include_launcher=1 PrependPath=1 Shortcuts=0" -Wait -NoNewWindow -PassThru
}

#------------------------------------------------------------------------------
# Install VCRedist
#------------------------------------------------------------------------------
If (Test-Path "$($ini[$bitPrograms]['VCRedistReg'])") {
    # Found VCRedist 2013, do nothing
    Write-Output " - VCRedist 2013 Found . . ."
} Else {
    Write-Output " - Downloading $($ini[$bitPrograms]['VCRedist']) . . ."
    $file = "$($ini[$bitPrograms]['VCRedist'])"
    $url  = "$($ini['Settings']['SaltRepo'])/$bitFolder/$file"
    $file = "$($ini['Settings']['DownloadDir'])\$bitFolder\$file"
    DownloadFileWithProgress $url $file

    Write-Output " - $script_name :: Installing $($ini[$bitPrograms]['VCRedist']) . . ."
    $p    = Start-Process $file -ArgumentList "/install /quiet /norestart" -Wait -NoNewWindow -PassThru
}

#------------------------------------------------------------------------------
# Update Environment Variables
#------------------------------------------------------------------------------
Write-Output " - Updating Environment Variables . . ."
$Path = (Get-ItemProperty -Path 'Registry::HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment' -Name PATH).Path
If (!($Path.ToLower().Contains("$($ini['Settings']['Scripts3Dir'])".ToLower()))) {
    $newPath  = "$($ini['Settings']['Scripts3Dir']);$Path"
    Set-ItemProperty -Path 'Registry::HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment' -Name PATH -Value $newPath
    $env:Path = $newPath
}

#==============================================================================
# Update PIP and SetupTools
#==============================================================================
Write-Output " ----------------------------------------------------------------"
Write-Output " - $script_name :: Updating PIP and SetupTools . . ."
Write-Output " ----------------------------------------------------------------"
Start_Process_and_test_exitcode "cmd" "/c $($ini['Settings']['Python3Dir'])\python.exe -m pip --disable-pip-version-check --no-cache-dir install -U pip `"setuptools<50.0.0`"" "python pip"


#==============================================================================
# Install pypi resources using pip
#==============================================================================
If ($NoPipDependencies -eq $false) {
  Write-Output " ----------------------------------------------------------------"
  Write-Output " - $script_name :: Installing pypi resources using pip . . ."
  Write-Output " ----------------------------------------------------------------"
  Start_Process_and_test_exitcode "cmd" "/c $($ini['Settings']['Python3Dir'])\python.exe -m pip --disable-pip-version-check --no-cache-dir install -r $($ini['Settings']['SrcDir'])\requirements\static\pkg\py$($ini['Settings']['PyVerMajor']).$($ini['Settings']['PyVerMinor'])\windows.txt" "pip install"
}

If (Test-Path "$($ini['Settings']['SitePkgs3Dir'])\pywin32_system32" -PathType Container )
{
    #==============================================================================
    # Cleaning Up PyWin32
    #==============================================================================
    Write-Output " ----------------------------------------------------------------"
    Write-Output " - $script_name :: Cleaning Up PyWin32 . . ."
    Write-Output " ----------------------------------------------------------------"

    # Move DLL's to Python Root
    # The dlls have to be in Python directory and the site-packages\win32 directory
    Write-Output " - $script_name :: Moving PyWin32 DLLs . . ."
    Copy-Item "$( $ini['Settings']['SitePkgs3Dir'] )\pywin32_system32\*.dll" "$( $ini['Settings']['Python3Dir'] )" -Force
    Move-Item "$( $ini['Settings']['SitePkgs3Dir'] )\pywin32_system32\*.dll" "$( $ini['Settings']['SitePkgs3Dir'] )\win32" -Force

    # Create gen_py directory
    Write-Output " - $script_name :: Creating gen_py Directory . . ."
    New-Item -Path "$( $ini['Settings']['SitePkgs3Dir'] )\win32com\gen_py" -ItemType Directory -Force | Out-Null

    # Remove pywin32_system32 directory
    Write-Output " - $script_name :: Removing pywin32_system32 Directory . . ."
    Remove-Item "$( $ini['Settings']['SitePkgs3Dir'] )\pywin32_system32"

    # Remove PyWin32 PostInstall and testall Scripts
    Write-Output " - $script_name :: Removing PyWin32 scripts . . ."
    Remove-Item "$( $ini['Settings']['Scripts3Dir'] )\pywin32_*" -Force -Recurse
}

#==============================================================================
# Copy DLLs to Python Directory
#==============================================================================
Write-Output " ----------------------------------------------------------------"
Write-Output "   - $script_name :: Copying DLLs . . ."
Write-Output " ----------------------------------------------------------------"
# Architecture Specific DLL's
ForEach($key in $ini[$bitDLLs].Keys) {
    Write-Output "   - $key . . ."
    $file = "$($ini[$bitDLLs][$key])"
    $url  = "$($ini['Settings']['SaltRepo'])/$bitFolder/$file"
    $file = "$($ini['Settings']['DownloadDir'])\$bitFolder\$file"
    DownloadFileWithProgress $url $file
    Copy-Item $file  -destination $($ini['Settings']['Python3Dir'])
}

#------------------------------------------------------------------------------
# Script complete
#------------------------------------------------------------------------------
Write-Output "================================================================="
Write-Output " $script_name :: Salt Stack Dev Environment Script Complete"
Write-Output "================================================================="
Write-Output ""

If (-Not $Silent) {
    Write-Output "Press any key to continue ..."
    $p = $HOST.UI.RawUI.Flushinputbuffer()
    $p = $HOST.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

#------------------------------------------------------------------------------
# Remove the temporary download directory
#------------------------------------------------------------------------------
Write-Output " ----------------------------------------------------------------"
Write-Output " - $script_name :: Cleaning up downloaded files"
Write-Output " ----------------------------------------------------------------"
Write-Output ""
Remove-Item $($ini['Settings']['DownloadDir']) -Force -Recurse
