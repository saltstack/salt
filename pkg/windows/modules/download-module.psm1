# Powershell supports only TLS 1.0 by default. Add support up to TLS 1.2
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]'Tls,Tls11,Tls12'

Function DownloadFileWithProgress {

    # Code for this function borrowed from http://poshcode.org/2461
    # Thanks Crazy Dave

    # This function downloads the passed file and shows a progress bar
    # It receives two parameters:
    #    $url - the file source
    #    $localfile - the file destination on the local machine

    param(
        [Parameter(Mandatory=$true)]
        [String] $url,
        [Parameter(Mandatory=$false)]
        [String] $localFile = (Join-Path $pwd.Path $url.SubString($url.LastIndexOf('/')))
    )


    begin {
        Write-Host -ForegroundColor DarkGreen "  download-module.DownloadFileWithProgress  $url"
        $client = New-Object System.Net.WebClient
        $Global:downloadComplete = $false
        $eventDataComplete = Register-ObjectEvent $client DownloadFileCompleted `
            -SourceIdentifier WebClient.DownloadFileComplete `
            -Action {$Global:downloadComplete = $true}
        $eventDataProgress = Register-ObjectEvent $client DownloadProgressChanged `
            -SourceIdentifier WebClient.DownloadProgressChanged `
            -Action { $Global:DPCEventArgs = $EventArgs }
    }
    process {
        Write-Progress -Activity 'Downloading file' -Status $url
        $client.DownloadFileAsync($url, $localFile)

        while (!($Global:downloadComplete)) {
            $pc = $Global:DPCEventArgs.ProgressPercentage
            if ($pc -ne $null) {
                Write-Progress -Activity 'Downloading file' -Status $url -PercentComplete $pc
            }
        }
        Write-Progress -Activity 'Downloading file' -Status $url -Complete
    }

    end {
        Unregister-Event -SourceIdentifier WebClient.DownloadProgressChanged
        Unregister-Event -SourceIdentifier WebClient.DownloadFileComplete
        $client.Dispose()
        $Global:downloadComplete = $null
        $Global:DPCEventArgs = $null
        Remove-Variable client
        Remove-Variable eventDataComplete
        Remove-Variable eventDataProgress
        [GC]::Collect()
        # 2016-07-06  mkr  Errorchecking added. nice-to-have: integration into the above code.
        If (!((Test-Path "$localfile") -and ((Get-Item "$localfile").length -gt 0kb))) {
            Write-Error "Exiting because download missing or zero-length:    $localfile"
            exit 2
        }

    }
}
