#
# Download url to file.
#
#
Param(
    [Parameter(Mandatory=$true)][string]$url,
    [Parameter(Mandatory=$true)][string]$file
)

Import-Module ./Modules/download-module.psm1

Write-Host -ForegroundColor Green "  download_url_file $url $file"
DownloadFileWithProgress $url $file

