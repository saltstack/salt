Set-PSDebug -Strict
Set-StrictMode -Version latest

$PROJECT_DIR  = Resolve-Path -Path $(git rev-parse --show-toplevel)
$SCRIPT_DIR   = (Get-ChildItem "$($myInvocation.MyCommand.Definition)").DirectoryName
$BUILD_DIR    = "$PROJECT_DIR\pkg\windows\build"
$MSI_DIR      = "$PROJECT_DIR\pkg\windows\msi"
$TEST_MSI     = "$MSI_DIR\test.msi"
$OLD_ROOT_DIR = "C:\Salt"
$NEW_ROOT_DIR = "C:\ProgramData\Salt Project\Salt"

#==============================================================================
# Check for Salt installation
#==============================================================================
$scrambled_salt_upgradecode = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UpgradeCodes\2A3BF6CFED569A14DA191DA004B26D14'
if (Test-Path $scrambled_salt_upgradecode) {
    Write-Host -ForegroundColor Red Salt must not be installed
    exit 1
}

#==============================================================================
# Check for Salt folders
#==============================================================================
if (Test-Path $NEW_ROOT_DIR) {
    Write-Host -ForegroundColor Red "`"$NEW_ROOT_DIR`" must not exist"
    exit 1
}

if (Test-Path $OLD_ROOT_DIR) {
    Write-Host -ForegroundColor Red "$OLD_ROOT_DIR must not exist"
    exit 1
}

if (Test-Path *.output) {
    Write-Host -ForegroundColor Red *.output must not exist
    exit 1
}


$MSIs = Get-ChildItem "$BUILD_DIR\*.msi"

$MSI_COUNT = ($MSIs | Measure-Object).Count

if ($MSI_COUNT -eq 0) {
    Write-Host -ForegroundColor Red *.msi must exist
    exit 1
}

if ($MSI_COUNT -gt 1) {
    Write-Host -ForegroundColor Red Only one *.msi must exist
    exit 1
}

$MSI = $MSIs[0]
Write-Host -ForegroundColor Yellow Testing ([System.IO.Path]::GetFileName($MSI))
Copy-Item -Path $MSI -Destination $TEST_MSI

$array_allowed_test_words = "dormant", "properties"
$exit_code = 0
foreach ( $testfilename in Get-ChildItem "$SCRIPT_DIR\*.test" ) {
    $dormant = $false    # test passes if and only if configuration is deleted on uninstall
    $rootdir = $NEW_ROOT_DIR     # default for each test
    $test_name = $testfilename.basename
    $batchfile = "$SCRIPT_DIR\$test_name.bat"
    $config_input = "$SCRIPT_DIR\$test_name.input"
    $minion_id = "$SCRIPT_DIR\$test_name.minion_id"
    $expected = "$SCRIPT_DIR\$test_name.expected"
    $generated = "$SCRIPT_DIR\$test_name.output"
    Write-Host -ForegroundColor Yellow -NoNewline ("{0,-65}" -f $test_name)

    foreach($line in Get-Content $testfilename) {
        if ($line.Length -eq 0) {continue}
        $words = $line -split " " , 2
        $head = $words[0]
        if ($words.length -eq 2){
            $tail = $words[1]
        } else {
            $tail = ""
        }
        if($array_allowed_test_words.Contains($head)){
            if ($head -eq "dormant") {
                $dormant = $true
            }
            if ($head -eq "properties") {
                Set-Content -Path $batchfile -Value "msiexec /i $TEST_MSI $tail /l*v `"$SCRIPT_DIR\$test_name.install.log`" /qb"
                if($tail.Contains("ROOTDIR=c:\salt")){
                    $rootdir = $OLD_ROOT_DIR
                }
            }
        } else {
            Write-Host -ForegroundColor Red $testfilename must not contain $head
            exit 1
        }
    }

    # Ensure rootdir/conf exists
    (New-Item -ItemType directory -Path "$rootdir\conf" -ErrorAction Ignore) | out-null

    if(Test-Path $config_input){
        Copy-Item -Path $config_input -Destination "$rootdir\conf\minion"
    }
    if(Test-Path $minion_id){
        Copy-Item -Path $minion_id -Destination "$rootdir\conf\minion_id"
    }

    # Run the install (via the batch file), which generates configuration (file conf/minion).
    $params = @{
        "FilePath" = "$Env:SystemRoot\system32\cmd.exe"
        "ArgumentList" = @(
            "/C"
            "$batchfile"
        )
        "Verb" = "runas"
        "PassThru" = $true
    }
    $exe_handling = start-process @params -WindowStyle hidden
    $exe_handling.WaitForExit()
    if (-not $?) {
        Write-Host -ForegroundColor Red "Install failed"
        exit 1
    }

    # Compare expected and generated configuration
    Copy-Item -Path "$rootdir\conf\minion" -Destination $generated

     if((Get-Content -Raw $expected) -eq (Get-Content -Raw $generated)){
        Remove-Item $generated
        Write-Host -ForegroundColor Green -NoNewline "content Pass "
    } else {
        # Leave generated config for analysis
        Write-Host -ForegroundColor Red -NoNewline "content Fail "
        $exit_code = 1
    }

    # Run uninstall
    $params = @{
        "FilePath" = "$Env:SystemRoot\system32\msiexec.exe"
        "ArgumentList" = @(
            "/X"
            "$TEST_MSI"
            "/qb"
            "/l*v"
            "$SCRIPT_DIR\$test_name.uninstall.log"
        )
        "Verb" = "runas"
        "PassThru" = $true
    }
    $exe_handling = start-process @params
    $exe_handling.WaitForExit()
    if (-not $?) {
        Write-Host -ForegroundColor Red "Uninstall failed"
        exit 1
    }

    #  Write-Host "    config exists after Uninstall $dormant  " (Test-Path "$rootdir\conf\minion")
    if($dormant -eq (Test-Path "$rootdir\conf\minion")){
        Write-Host -ForegroundColor Green " dormancy Pass"
    } else {
        # If a dormancy test fails, overall testing will be a failure, but continue testing
        Write-Host -ForegroundColor Red " dormancy Fail"
        $exit_code = 1
    }

    # Clean up system from the last test config
    Remove-Item -Path $OLD_ROOT_DIR -Recurse -Force -ErrorAction Ignore | Out-Null
    Remove-Item -Path $NEW_ROOT_DIR -Recurse -Force -ErrorAction Ignore | Out-Null
}

# Clean up copied msi
Remove-Item $TEST_MSI

if ($exit_code -eq 0) {
    Write-Host "All tests completed successfully" -ForegroundColor Green
} else {
    Write-Host "Tests completed with failures" -ForegroundColor Red
}

exit $exit_code
