Function Expand-ZipFile($zipfile, $destination) {

    # This function unzips a zip file
    # Code obtained from:
    # http://www.howtogeek.com/tips/how-to-extract-zip-files-using-powershell/

    # Create a new directory if it doesn't exist
    If (!(Test-Path -Path $destination)) {
        $p = New-Item -ItemType directory -Path $destination
    }

    # Define Objects
    $objShell = New-Object -Com Shell.Application

    # Open the zip file
    $objZip = $objShell.NameSpace($zipfile)

    # Unzip each item in the zip file
    ForEach($item in $objZip.Items()) {
        $objShell.Namespace($destination).CopyHere($item, 0x14)
    }
}