Function Start_Process_and_test_exitcode {

    # This function is a wrapper for Start-Process that checks the exitcode
    # It receives 3 parameters:
    #    $fun   - the process that shall be started
    #    $args  - the the arguments of $fun
    #    $descr - the short description shown in the case of an error

    Param(
        [Parameter(Mandatory=$true)] [String] $fun,
        [Parameter(Mandatory=$true)] [String] $args,
        [Parameter(Mandatory=$true)] [String] $descr
    )

    Begin { Write-Host "Executing Command: $fun $args" }

    Process {
        $p = Start-Process "$fun" -ArgumentList "$args" -Wait -NoNewWindow -PassThru
        If ($p.ExitCode -ne 0) {
            Write-Error "$descr returned exitcode $p.ExitCode."
            exit $p.ExitCode
        }
    }

    End { Write-Host "Finished Executing Command: $fun $args" }
}
