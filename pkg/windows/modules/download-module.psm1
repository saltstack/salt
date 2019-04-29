# Powershell supports only TLS 1.0 by default. Add support up to TLS 1.2
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]'Tls,Tls11,Tls12'

Function DownloadFileWithProgress {

    # Code for this function borrowed from http://poshcode.org/2461
    # Thanks Crazy Dave

    # This function downloads the passed file and shows a progress bar
    # It receives two parameters:
    #    $url - the file source
    #    $localfile - the file destination on the local machine

    # Originally, DownLoadDir is deleted for each install, therefore
    # this function did not expect that the file exists.
    # You may want to set an environment variable SALTREPO_LOCAL_CACHE, a cache which lives as long as you decide.
    # Therefore this function must test if the file exists.


    param(
        [Parameter(Mandatory=$true)]
        [String] $url,
        [Parameter(Mandatory=$false)]
        [String] $localFile = (Join-Path $pwd.Path $url.SubString($url.LastIndexOf('/')))
    )

    begin {
        $Global:NEED_PROCESS_AND_END = $true
        Write-Verbose " **** DownloadFileWithProgress looking for **** $localFile ********"
        if ( [bool]$Env:SALTREPO_LOCAL_CACHE -and (Test-Path $localFile) ) {
            Write-Verbose " **** found **** $localFile ********"
            $Global:NEED_PROCESS_AND_END = $false
        } else {
            Write-Verbose " ++++++ BEGIN DOWNLOADING ++++++ $localFile +++++++"
            $client = New-Object System.Net.WebClient
            $Global:downloadComplete = $false
            $eventDataComplete = Register-ObjectEvent $client DownloadFileCompleted `
            -SourceIdentifier WebClient.DownloadFileComplete `
            -Action {$Global:downloadComplete = $true}
            $eventDataProgress = Register-ObjectEvent $client DownloadProgressChanged `
            -SourceIdentifier WebClient.DownloadProgressChanged `
            -Action { $Global:DPCEventArgs = $EventArgs }
        }
}
    process {
        if ( $Global:NEED_PROCESS_AND_END ) {
            Write-Verbose " ++++++ actually DOWNLOADING ++++++ $localFile +++++++"
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
    }

    end {
        if ( $Global:NEED_PROCESS_AND_END ) {
            Unregister-Event -SourceIdentifier WebClient.DownloadProgressChanged
            Unregister-Event -SourceIdentifier WebClient.DownloadFileComplete
            $client.Dispose()
            $Global:downloadComplete = $null
            $Global:DPCEventArgs     = $null
            Remove-Variable client
            Remove-Variable eventDataComplete
            Remove-Variable eventDataProgress
            [GC]::Collect()
            # Errorchecking
            If (!((Test-Path "$localfile") -and ((Get-Item "$localfile").length -gt 0kb))) {
                Write-Error "download-module.psm1 exits in error, download is missing or has zero-length: $localfile"
                exit 2
            }
        }
    }
}