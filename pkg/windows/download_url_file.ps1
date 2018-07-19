#
# ps1 wrapper for psm1
#
#
Param(
    [Parameter(Mandatory=$true)][string]$url,
    [Parameter(Mandatory=$true)][string]$file
)

Import-Module ./Modules/download-module.psm1

DownloadFileWithProgress $url $file

