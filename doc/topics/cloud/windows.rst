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

* `OpenSuse Build Service`__

.. __: http://software.opensuse.org/package/winexe

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

    userdata_file: /etc/salt/windows-firewall.ps1


Configuration
=============
Configuration is set as usual, with some extra configuration settings. The
location of the Windows installer on the machine that Salt Cloud is running on
must be specified. This may be done in any of the regular configuration files
(main, providers, profiles, maps). For example:

Setting the installer in ``/etc/salt/cloud.providers``:

.. code-block:: yaml

    my-softlayer:
      provider: softlayer
      user: MYUSER1138
      apikey: 'e3b68aa711e6deadc62d5b76355674beef7cc3116062ddbacafe5f7e465bfdc9'
      minion:
        master: saltmaster.example.com
      win_installer: /root/Salt-Minion-2014.7.0-AMD64-Setup.exe
      win_username: Administrator
      win_password: letmein

The default Windows user is `Administrator`, and the default Windows password
is blank.


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
