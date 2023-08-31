<powershell>
New-NetFirewallRule -Name "SMB445" -DisplayName "SMB445" -Protocol TCP -LocalPort 445
New-NetFirewallRule -Name "WINRM5986" -DisplayName "WINRM5986" -Protocol TCP -LocalPort 5986

winrm quickconfig -q
winrm set winrm/config/winrs '@{MaxMemoryPerShellMB="300"}'
winrm set winrm/config '@{MaxTimeoutms="1800000"}'
winrm set winrm/config/service/auth '@{Basic="true"}'

$SourceStoreScope = 'LocalMachine'
$SourceStorename = 'Remote Desktop'

$SourceStore = New-Object -TypeName System.Security.Cryptography.X509Certificates.X509Store -ArgumentList $SourceStorename, $SourceStoreScope
$SourceStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)

$cert = $SourceStore.Certificates | Where-Object -FilterScript {
    $_.subject -like '*'
}

$DestStoreScope = 'LocalMachine'
$DestStoreName = 'My'

$DestStore = New-Object -TypeName System.Security.Cryptography.X509Certificates.X509Store -ArgumentList $DestStoreName, $DestStoreScope
$DestStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
$DestStore.Add($cert)

$SourceStore.Close()
$DestStore.Close()

winrm create winrm/config/listener?Address=*+Transport=HTTPS `@`{CertificateThumbprint=`"($cert.Thumbprint)`"`}

Restart-Service winrm
</powershell>
