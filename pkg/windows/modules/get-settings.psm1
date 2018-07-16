Function Get-Settings {

    [CmdletBinding()]
    Param()

    Begin
        {Write-Verbose "$($MyInvocation.MyCommand.Name):: Function started"}

    Process
    {
        Write-Verbose "$($MyInvocation.MyCommand.Name):: Loading Settings"

        $ini = @{}

        # Location where the files are kept
        $Settings = @{
            "SaltRepo"    = "https://repo.saltstack.com/windows/dependencies"
            "SaltDir"     = "C:\salt"
            "Python2Dir"   = "C:\Python27"
            "Scripts2Dir"  = "C:\Python27\Scripts"
            "SitePkgs2Dir" = "C:\Python27\Lib\site-packages"
            "Python3Dir"   = "C:\Python35"
            "Scripts3Dir"  = "C:\Python35\Scripts"
            "SitePkgs3Dir" = "C:\Python35\Lib\site-packages"
            "DownloadDir" = "$env:Temp\DevSalt"
            }
        # The script deletes the DownLoadDir (above) for each install.
        # You may want to set an environment variable SALTREPO_LOCAL_CACHE, a cache which lives as long as you decide.
        if ( [bool]$Env:SALTREPO_LOCAL_CACHE ) {
          $Settings.Set_Item("DownloadDir", "$Env:SALTREPO_LOCAL_CACHE")
        }

        $ini.Add("Settings", $Settings)
        Write-Verbose "DownloadDir === $($ini['Settings']['DownloadDir']) ==="

        # Prerequisite software
        $Prerequisites = @{
            "NSIS"           = "nsis-3.03-setup.exe"
            "VCforPython"    = "VCForPython27.msi"
            "VCppBuildTools" = "visualcppbuildtools_full.exe"
        }
        $ini.Add("Prerequisites", $Prerequisites)

        # Location of programs on 64 bit Windows
        $64bitPaths = @{
            "NSISDir"           = "C:\Program Files (x86)\NSIS"
            "VCforPythonDir"    = "C:\Program Files (x86)\Common Files\Microsoft\Visual C++ for Python\9.0"
            "VCppBuildToolsDir" = "C:\Program Files (x86)\Microsoft Visual C++ Build Tools"
        }
        $ini.Add("64bitPaths", $64bitPaths)

        # Location of programs on 32 bit Windows
        $32bitPaths = @{
            "NSISDir"           = "C:\Program Files\NSIS"
            "VCforPythonDir"    = "C:\Program Files\Common Files\Microsoft\Visual C++ for Python\9.0"
            "VCppBuildToolsDir" = "C:\Program Files\Microsoft Visual C++ Build Tools"
        }
        $ini.Add("32bitPaths", $32bitPaths)

        # Filenames for 64 bit Windows
        $64bitPrograms = @{
            "Python2"   = "python-2.7.14.amd64.msi"
            "Python3"   = "python-3.5.3-amd64.exe"
        }
        $ini.Add("64bitPrograms", $64bitPrograms)

        # Filenames for 32 bit Windows
        $32bitPrograms = @{
            "Python2"   = "python-2.7.14.msi"
            "Python3"   = "python-3.5.3.exe"
        }
        $ini.Add("32bitPrograms", $32bitPrograms)

        # DLL's for 64 bit Windows
        $64bitDLLs = @{
            "Libeay"     = "libeay32.dll"
            "SSLeay"     = "ssleay32.dll"
            "OpenSSLLic" = "OpenSSL_License.txt"
            "msvcr"      = "msvcr120.dll"
            "Libsodium"  = "libsodium.dll"
        }
        $ini.Add("64bitDLLs", $64bitDLLs)

        # DLL's for 32 bit Windows
        $32bitDLLs = @{
            "Libeay"     = "libeay32.dll"
            "SSLeay"     = "ssleay32.dll"
            "OpenSSLLic" = "OpenSSL_License.txt"
            "msvcr"      = "msvcr120.dll"
            "Libsodium"  = "libsodium.dll"
        }
        $ini.Add("32bitDLLs", $32bitDLLs)

        Write-Verbose "$($MyInvocation.MyCommand.Name):: Finished Loading Settings"
        Return $ini
    }
    End
        {Write-Verbose "$($MyInvocation.MyCommand.Name):: Function ended"}
}
