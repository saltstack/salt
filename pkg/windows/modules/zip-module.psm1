Function Expand-ZipFile {

    Param(
        [Parameter(Mandatory = $true)] [string] $zipfile,
        [Parameter(Mandatory = $true)] [string] $destination
    )
    # This function unzips a zip file
    # Code obtained from:
    # http://www.howtogeek.com/tips/how-to-extract-zip-files-using-powershell/

    Begin { Write-Host " - Unzipping '$zipfile' to '$destination'" }

    Process {
        # Create a new directory if it doesn't exist
        If (!(Test-Path -Path $destination))
        {
            New-Item -ItemType directory -Path $destination
        }

        # Define Objects
        $objShell = New-Object -Com Shell.Application

        # Open the zip file
        $objZip = $objShell.NameSpace($zipfile)

        # Unzip each item in the zip file
        ForEach ($item in $objZip.Items())
        {
            $objShell.Namespace($destination).CopyHere($item, 0x14)
        }
    }

    End { Write-Host " - Finished"}
}
