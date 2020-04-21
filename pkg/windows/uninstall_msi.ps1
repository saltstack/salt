#
# Uninstalls the Salt-Minion from an msi install. 
# Use the (scrambled) msi upgrade code to find the (scrambled) product code
# Precondition: you must ensure the Registry key exists.
# This script is a short version of https://github.com/markuskramerIgitt/salt-windows-msi/blob/master/uninst.ps1
#
#

$upgradecodeRegKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UpgradeCodes\2A3BF6CFED569A14DA191DA004B26D14'
# The scrambled product code is the only entry
$scrambledProductcode = $((Get-ItemProperty $upgradecodeRegKey).PSObject.Properties)[0].Name.ToString()
# Unscramble: reverse chunks
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
& msiexec /x $productcode /qb
