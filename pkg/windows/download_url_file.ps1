#
# Download url to file. Optionally, store in cache
#
#
Param(
    [Parameter(Mandatory=$true)][string]$url,
    [Parameter(Mandatory=$true)][string]$file
)


$VerbosePreference = 'Continue'


Import-Module ./Modules/download-module.psm1

if ( [bool]$Env:SALTREPO_LOCAL_CACHE) {
    Write-Verbose "found SALTREPO_LOCAL_CACHE environment variable $Env:SALTREPO_LOCAL_CACHE"
} else {
    Write-Verbose "no SALTREPO_LOCAL_CACHE environment variable "
}

$saltrepo_url = "http://repo.saltstack.com/windows/dependencies/"

if ( [bool]$Env:SALTREPO_LOCAL_CACHE -And $url.StartsWith($saltrepo_url) ) {
    Write-Verbose "found SALTREPO_LOCAL_CACHE environment variable and url is saltrepo"
    $url_relative__slash     = $url                 -replace [regex]::Escape($saltrepo_url), ""
    $url_relative__backslash = $url_relative__slash -replace [regex]::Escape("/"), "\\"
    $localCacheFile          = Join-Path $Env:SALTREPO_LOCAL_CACHE $url_relative__backslash
    if (-Not (Test-Path $localCacheFile)) {
        Write-Verbose "downloading to cache   $localCacheFile"
        DownloadFileWithProgress $url $localCacheFile
    }
    Write-Verbose "copying from cache $file"
    Copy-Item $localCacheFile  -destination $file
} else {
    Write-Verbose "no SALTREPO_LOCAL_CACHE environment variable, or URL not saltrepo, downloading directly"
    DownloadFileWithProgress $url $file
}

