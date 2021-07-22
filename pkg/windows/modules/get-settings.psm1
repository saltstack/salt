Function Get-Settings {

    [CmdletBinding()]
    Param()

    Begin
        {Write-Verbose "$($MyInvocation.MyCommand.Name):: Function started"}

    Process
    {
        Write-Verbose "$($MyInvocation.MyCommand.Name):: Loading Settings"

        $ini = @{}

        If ( -Not (Test-Path env:SrcDir)) {
            $env:SrcDir = $(git rev-parse --show-toplevel).Replace("/", "\")
        }
        If ( -Not (Test-Path env:PyVerMajor)) { $env:PyVerMajor = "3" }
        If ( -Not (Test-Path env:PyVerMinor)) { $env:PyVerMinor = "7" }
        If ( -Not (Test-Path env:PyDir)) { $env:PyDir = "C:\Python37" }

        # Location where the files are kept
        $Settings = @{
            "SrcDir"       = "$env:SrcDir"
            "SaltRepo"     = "https://repo.saltstack.com/windows/dependencies"
            "SaltDir"      = "C:\salt"
            "PyVerMajor"   = "$env:PyVerMajor"
            "PyVerMinor"   = "$env:PyVerMinor"
            "Python3Dir"   = "$env:PyDir"
            "Scripts3Dir"  = "$env:PyDir\Scripts"
            "SitePkgs3Dir" = "$env:PyDir\Lib\site-packages"
            "DownloadDir"  = "$env:Temp\DevSalt"
            }

        $ini.Add("Settings", $Settings)
        Write-Verbose "DownloadDir === $($ini['Settings']['DownloadDir']) ==="

        # Prerequisite software
        $Prerequisites = @{
            "NSIS"             = "nsis-3.03-setup.exe"
            "NSISPluginEnVar"  = "nsis-plugin-envar.zip"
            "NSISPluginUnzipA" = "nsis-plugin-nsisunz.zip"
            "NSISPluginUnzipU" = "nsis-plugin-nsisunzu.zip"
            "VS2015BuildTools" = "vcppbuildtools_full.zip"
        }
        $ini.Add("Prerequisites", $Prerequisites)

        # Location of programs on 64 bit Windows
        $64bitPaths = @{
            "NSISDir"              = "C:\Program Files (x86)\NSIS"
            "NSISPluginsDirA"      = "C:\Program Files (x86)\NSIS\Plugins\x86-ansi"
            "NSISPluginsDirU"      = "C:\Program Files (x86)\NSIS\Plugins\x86-unicode"
            "VCforPythonDir"       = "C:\Program Files (x86)\Common Files\Microsoft\Visual C++ for Python\9.0"
            "VS2015BuildToolsDir"  = "C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\bin"
        }
        $ini.Add("64bitPaths", $64bitPaths)

        # Location of programs on 32 bit Windows
        $32bitPaths = @{
            "NSISDir"              = "C:\Program Files\NSIS"
            "NSISPluginsDirA"      = "C:\Program Files\NSIS\Plugins\x86-ansi"
            "NSISPluginsDirU"      = "C:\Program Files\NSIS\Plugins\x86-unicode"
            "VCforPythonDir"       = "C:\Program Files\Common Files\Microsoft\Visual C++ for Python\9.0"
            "VS2015BuildToolsDir"  = "C:\Program Files\Microsoft Visual Studio 14.0\VC\bin"
        }
        $ini.Add("32bitPaths", $32bitPaths)

        # Filenames for 64 bit Windows
        $64bitPrograms = @{
            "Python3"     = "python-3.7.4-amd64.exe"
            "VCRedist"    = "vcredist_x64_2013.exe"
            "VCRedistReg" = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{53CF6934-A98D-3D84-9146-FC4EDF3D5641}"
        }
        $ini.Add("64bitPrograms", $64bitPrograms)

        # Filenames for 32 bit Windows
        $32bitPrograms = @{
            "Python3"     = "python-3.7.4.exe"
            "VCRedist"    = "vcredist_x86_2013.exe"
            "VCRedistReg" = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{8122DAB1-ED4D-3676-BB0A-CA368196543E}"
        }
        $ini.Add("32bitPrograms", $32bitPrograms)

        # DLL's for 64 bit Windows
        $64bitDLLs = @{
            "Libeay"     = "libeay32.dll"
            "SSLeay"     = "ssleay32.dll"
            "OpenSSLLic" = "OpenSSL_License.txt"
            "Libsodium"  = "libsodium.dll"
        }
        $ini.Add("64bitDLLs", $64bitDLLs)

        # DLL's for 32 bit Windows
        $32bitDLLs = @{
            "Libeay"     = "libeay32.dll"
            "SSLeay"     = "ssleay32.dll"
            "OpenSSLLic" = "OpenSSL_License.txt"
            "Libsodium"  = "libsodium.dll"
        }
        $ini.Add("32bitDLLs", $32bitDLLs)

        Write-Verbose "$($MyInvocation.MyCommand.Name):: Finished Loading Settings"
        Return $ini
    }
    End
        {Write-Verbose "$($MyInvocation.MyCommand.Name):: Function ended"}
}
