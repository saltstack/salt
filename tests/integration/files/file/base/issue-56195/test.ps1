[CmdLetBinding()]
Param(
  [SecureString] $SecureString
)

$Credential = New-Object System.Net.NetworkCredential("DummyId", $SecureString)
$Credential.Password
