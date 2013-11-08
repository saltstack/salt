===========================
Spinning up Windows Minions
===========================

It is possible to use Salt Cloud to spin up Windows instances, and then install
Salt on them. This functionality is available on all cloud providers that are
supported by Salt Cloud. However, it may not necessarily be available on all
Windows images.

Requirements
============
Salt Cloud makes use of `smbclient` and `winexe` to set up the Windows Salt
Minion installer. `smbclient` may be part of either the `samba` package, or its
own `smbclient` package, depending on the distribution. `winexe` is less
commonly available in distribution-specific repositories. However, it is
currently being built for various distributions in 3rd party channels:

* `RPMs at pbone.net`__
.. __: http://rpm.pbone.net/index.php3?stat=3&search=winexe

* `OpenSuse Build Service`__
.. __: http://software.opensuse.org/package/winexe

Additionally, a copy of the Salt Minion Windows installer must be present on
the system on which Salt Cloud is running. This installer may be downloaded
from saltstack.com:

* `SaltStack Download Area`__
.. __: http://saltstack.com/downloads/


Firewall Settings
=================
Because Salt Cloud makes use of `smbclient` and `winexe`, port 445 must be open
on the target image. This port is not generally open by default on a standard
Windows distribution, and care must be taken to use an image in which this port
is open, or the Windows firewall is disabled.


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
      win_installer: /root/Salt-Minion-0.17.0-AMD64-Setup.exe
      win_username: Administrator
      win_password: letmein

The default Windows user is `Administrator`, and the default Windows password
is blank.

