===========================
Spinning up Windows Minions
===========================

It is possible to use Salt Cloud to spin up Windows instances, and then install
Salt on them. This functionality is available on all cloud providers that are
supported by Salt Cloud. However, it may not necessarily be available on all
Windows images.

Requirements
============
Salt Cloud makes use of `impacket` and `winexe` to set up the Windows Salt
Minion installer.

`impacket` is usually available as either the `impacket` or the
`python-impacket` package, depending on the distribution. More information on
`impacket` can be found at the project home:

* `impacket project home`__

.. __: https://code.google.com/p/impacket/

`winexe` is less commonly available in distribution-specific repositories.
However, it is currently being built for various distributions in 3rd party
channels:

* `RPMs at pbone.net`__

.. __: http://rpm.pbone.net/index.php3?stat=3&search=winexe

* `openSUSE Build Service`__

.. __: http://software.opensuse.org/package/winexe

Optionally WinRM can be used instead of `winexe` if the python module `pywinrm`
is available and WinRM is supported on the target Windows version. Information
on pywinrm can be found at the project home:

* `pywinrm project home`__

.. __: https://github.com/diyan/pywinrm

Additionally, a copy of the Salt Minion Windows installer must be present on
the system on which Salt Cloud is running. This installer may be downloaded
from saltstack.com:

* `SaltStack Download Area`__

.. __: https://repo.saltstack.com/windows/


Firewall Settings
=================
Because Salt Cloud makes use of `smbclient` and `winexe`, port 445 must be open
on the target image. This port is not generally open by default on a standard
Windows distribution, and care must be taken to use an image in which this port
is open, or the Windows firewall is disabled.

If supported by the cloud provider, a PowerShell script may be used to open up
this port automatically, using the cloud provider's `userdata`. The following
script would open up port 445, and apply the changes:

.. code-block:: powershell

    <powershell>
    New-NetFirewallRule -Name "SMB445" -DisplayName "SMB445" -Protocol TCP -LocalPort 445
    Set-Item (dir wsman:\localhost\Listener\*\Port -Recurse).pspath 445 -Force
    Restart-Service winrm
    </powershell>

For EC2, this script may be saved as a file, and specified in the provider or
profile configuration as `userdata_file`. For instance:

.. code-block:: yaml

    my-ec2-config:
      # Pass userdata to the instance to be created
      userdata_file: /etc/salt/windows-firewall.ps1

.. note::
    From versions 2016.11.0 and 2016.11.3, this file was passed through the
    master's :conf_master:`renderer` to template it. However, this caused
    issues with non-YAML data, so templating is no longer performed by default.
    To template the userdata_file, add a ``userdata_template`` option to the
    cloud profile:

    .. code-block:: yaml

        my-ec2-config:
          # Pass userdata to the instance to be created
          userdata_file: /etc/salt/windows-firewall.ps1
          userdata_template: jinja

    If no ``userdata_template`` is set in the cloud profile, then the master
    configuration will be checked for a :conf_master:`userdata_template` value.
    If this is not set, then no templating will be performed on the
    userdata_file.

    To disable templating in a cloud profile when a
    :conf_master:`userdata_template` has been set in the master configuration
    file, simply set ``userdata_template`` to ``False`` in the cloud profile:

    .. code-block:: yaml

        my-ec2-config:
          # Pass userdata to the instance to be created
          userdata_file: /etc/salt/windows-firewall.ps1
          userdata_template: False


If you are using WinRM on EC2 the HTTPS port for the WinRM service must also be
enabled in your userdata. By default EC2 Windows images only have insecure HTTP
enabled. To enable HTTPS and basic authentication required by pywinrm consider
the following userdata example:

.. code-block:: powershell

    <powershell>
    New-NetFirewallRule -Name "SMB445" -DisplayName "SMB445" -Protocol TCP -LocalPort 445
    New-NetFirewallRule -Name "WINRM5986" -DisplayName "WINRM5986" -Protocol TCP -LocalPort 5986

    winrm quickconfig -q
    winrm set winrm/config/winrs '@{MaxMemoryPerShellMB="300"}'
    winrm set winrm/config '@{MaxTimeoutms="1800000"}'
    winrm set winrm/config/service/auth '@{Basic="true"}'

    $SourceStoreScope = 'LocalMachine'
    $SourceStorename = 'Remote Desktop'

    $SourceStore = New-Object  -TypeName System.Security.Cryptography.X509Certificates.X509Store  -ArgumentList $SourceStorename, $SourceStoreScope
    $SourceStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)

    $cert = $SourceStore.Certificates | Where-Object  -FilterScript {
        $_.subject -like '*'
    }

    $DestStoreScope = 'LocalMachine'
    $DestStoreName = 'My'

    $DestStore = New-Object  -TypeName System.Security.Cryptography.X509Certificates.X509Store  -ArgumentList $DestStoreName, $DestStoreScope
    $DestStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $DestStore.Add($cert)

    $SourceStore.Close()
    $DestStore.Close()

    winrm create winrm/config/listener?Address=*+Transport=HTTPS  `@`{Hostname=`"($certId)`"`;CertificateThumbprint=`"($cert.Thumbprint)`"`}

    Restart-Service winrm
    </powershell>

No certificate store is available by default on EC2 images and creating
one does not seem possible without an MMC (cannot be automated). To use the
default EC2 Windows images the above copies the RDP store.

Configuration
=============
Configuration is set as usual, with some extra configuration settings. The
location of the Windows installer on the machine that Salt Cloud is running on
must be specified. This may be done in any of the regular configuration files
(main, providers, profiles, maps). For example:

Setting the installer in ``/etc/salt/cloud.providers``:

.. code-block:: yaml

    my-softlayer:
      driver: softlayer
      user: MYUSER1138
      apikey: 'e3b68aa711e6deadc62d5b76355674beef7cc3116062ddbacafe5f7e465bfdc9'
      minion:
        master: saltmaster.example.com
      win_installer: /root/Salt-Minion-2014.7.0-AMD64-Setup.exe
      win_username: Administrator
      win_password: letmein
      smb_port: 445

The default Windows user is `Administrator`, and the default Windows password
is blank.

If WinRM is to be used ``use_winrm`` needs to be set to `True`. ``winrm_port``
can be used to specify a custom port (must be HTTPS listener).


Auto-Generated Passwords on EC2
===============================
On EC2, when the `win_password` is set to `auto`, Salt Cloud will query EC2 for
an auto-generated password. This password is expected to take at least 4 minutes
to generate, adding additional time to the deploy process.

When the EC2 API is queried for the auto-generated password, it will be returned
in a message encrypted with the specified `keyname`. This requires that the
appropriate `private_key` file is also specified. Such a profile configuration
might look like:

.. code-block:: yaml

    windows-server-2012:
      provider: my-ec2-config
      image: ami-c49c0dac
      size: m1.small
      securitygroup: windows
      keyname: mykey
      private_key: /root/mykey.pem
      userdata_file: /etc/salt/windows-firewall.ps1
      win_installer: /root/Salt-Minion-2014.7.0-AMD64-Setup.exe
      win_username: Administrator
      win_password: auto
