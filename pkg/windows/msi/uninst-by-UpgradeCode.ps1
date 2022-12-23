# Uninstalls the Salt-Minion using the msi upgrade code
$upgradecodeRegKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UpgradeCodes\2A3BF6CFED569A14DA191DA004B26D14'


if (Test-Path $upgradecodeRegKey) {           # The scrambled product code is the only entry
    $scrambledProductcode = $((Get-ItemProperty $upgradecodeRegKey).PSObject.Properties)[0].Name.ToString()
    if ($scrambledProductcode -match '^[0-9A-Z]{32}$') {            # Reverse chunks
        #Write-Host -ForegroundColor Yellow $scrambledProductcode.Insert(20,'-').Insert(16,'-').Insert(12,'-').Insert(8,'-')
        $productcode = ""
        $lastIndex = 0
        foreach ($index in @(8, 4, 4, 2, 2, 2, 2, 2, 2, 2, 2)) {
            $chunk = $scrambledProductcode.Substring($lastIndex, $index) -split ''
            [array]::Reverse($chunk)
            $productcode += $chunk -join ''
            $lastIndex += $index
        }
        # Format productcode with dashes and curly braces
        $productcode = $productcode.Insert(20,'-').Insert(16,'-').Insert(12,'-').Insert(8,'-')
        $productcode = "{$productcode}"
        Write-Host -ForegroundColor Yellow msiexec...
        $msiexitcode = (Start-Process -FilePath "msiexec.exe" -ArgumentList "/x $productcode /qb" -Wait -Passthru).ExitCode
        Write-Host -ForegroundColor Yellow "msiexec... exited with code $msiexitcode"
    } else {
        Write-Host -ForegroundColor Red Cannot uninstall
        exit(1)
    }
} else {
    Write-Host -ForegroundColor Blue Not installed
}
