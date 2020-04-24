.. _getting-started-with-saltify:

============================
Getting Started With Saltify
============================

The Saltify driver is a driver for installing Salt on existing
machines (virtual or bare metal).


Dependencies
============
The Saltify driver has no external dependencies.


Configuration
=============

Because the Saltify driver does not use an actual cloud provider host, it can have a
simple provider configuration. The only thing that is required to be set is the
driver name, and any other potentially useful information, like the location of
the salt-master:

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers file or any file in
    # the /etc/salt/cloud.providers.d/ directory.

    my-saltify-config:
      minion:
        master: 111.222.333.444
      driver: saltify

However, if you wish to use the more advanced capabilities of salt-cloud, such as
rebooting, listing, and disconnecting machines, then the salt master must fill
the role usually performed by a vendor's cloud management system. The salt master
must be running on the salt-cloud machine, and created nodes must be connected to the
master.

Additional information about which configuration options apply to which actions
can be studied in the
:ref:`Saltify Module documentation <saltify-module>`
and the
:ref:`Miscellaneous Salt Cloud Options <misc-salt-cloud-options>`
document.

Profiles
========

Saltify requires a separate profile to be configured for each machine that
needs Salt installed [#]_. The initial profile can be set up at
``/etc/salt/cloud.profiles``
or in the ``/etc/salt/cloud.profiles.d/`` directory. Each profile requires
both an ``ssh_host`` and an ``ssh_username`` key parameter as well as either
an ``key_filename`` or a ``password``.

.. [#] Unless you are using a map file to provide the unique parameters.

Profile configuration example:

.. code-block:: yaml

    # /etc/salt/cloud.profiles.d/saltify.conf

    salt-this-machine:
      ssh_host: 12.34.56.78
      ssh_username: root
      key_filename: '/etc/salt/mysshkey.pem'
      provider: my-saltify-config

The machine can now be "Salted" with the following command:

.. code-block:: bash

    salt-cloud -p salt-this-machine my-machine

This will install salt on the machine specified by the cloud profile,
``salt-this-machine``, and will give the machine the minion id of
``my-machine``. If the command was executed on the salt-master, its Salt
key will automatically be accepted by the master.

Once a salt-minion has been successfully installed on the instance, connectivity
to it can be verified with Salt:

.. code-block:: bash

    salt my-machine test.version

Destroy Options
---------------

.. versionadded:: 2018.3.0

For obvious reasons, the ``destroy`` action does not actually vaporize hardware.
If the salt  master is connected, it can tear down parts of the client machines.
It will remove the client's key from the salt master,
and can execute the following options:

.. code-block:: yaml

  - remove_config_on_destroy: true
    # default: true
    # Deactivate salt-minion on reboot and
    # delete the minion config and key files from its "/etc/salt" directory,
    #   NOTE: If deactivation was unsuccessful (older Ubuntu machines) then when
    #   salt-minion restarts it will automatically create a new, unwanted, set
    #   of key files. Use the "force_minion_config" option to replace them.

  - shutdown_on_destroy: false
    # default: false
    # last of all, send a "shutdown" command to the client.

Wake On LAN
-----------

.. versionadded:: 2018.3.0

In addition to connecting a hardware machine to a Salt master,
you have the option of sending a wake-on-LAN
`magic packet`_
to start that machine running.

.. _magic packet: https://en.wikipedia.org/wiki/Wake-on-LAN

The "magic packet" must be sent by an existing salt minion which is on
the same network segment as the target machine. (Or your router
must be set up especially to route WoL packets.) Your target machine
must be set up to listen for WoL and to respond appropriately.

You must provide the Salt node id of the machine which will send
the WoL packet \(parameter ``wol_sender_node``\), and
the hardware MAC address of the machine you intend to wake,
\(parameter ``wake_on_lan_mac``\). If both parameters are defined,
the WoL will be sent. The cloud master will then sleep a while
\(parameter ``wol_boot_wait``) to give the target machine time to
boot up before we start probing its SSH port to begin deploying
Salt to it. The default sleep time is 30 seconds.

.. code-block:: yaml

    # /etc/salt/cloud.profiles.d/saltify.conf

    salt-this-machine:
      ssh_host: 12.34.56.78
      ssh_username: root
      key_filename: '/etc/salt/mysshkey.pem'
      provider: my-saltify-config
      wake_on_lan_mac: '00:e0:4c:70:2a:b2'  # found with ifconfig
      wol_sender_node: bevymaster  # its on this network segment
      wol_boot_wait: 45  # seconds to sleep

Using Map Files
---------------
The settings explained in the section above may also be set in a map file. An
example of how to use the Saltify driver with a map file follows:

.. code-block:: yaml

    # /etc/salt/saltify-map

    make_salty:
      - my-instance-0:
          ssh_host: 12.34.56.78
          ssh_username: root
          password: very-bad-password
      - my-instance-1:
          ssh_host: 44.33.22.11
          ssh_username: root
          password: another-bad-pass

In this example, the names ``my-instance-0`` and ``my-instance-1`` will be the
identifiers of the deployed minions.

Note: The ``ssh_host`` directive is also used for Windows hosts, even though they do
not typically run the SSH service. It indicates IP address or host name for the target
system.

Note: When using a cloud map with the Saltify driver, the name of the profile
to use, in this case ``make_salty``, must be defined in a profile config. For
example:

.. code-block:: yaml

    # /etc/salt/cloud.profiles.d/saltify.conf

    make_salty:
      provider: my-saltify-config

The machines listed in the map file can now be "Salted" by applying the
following salt map command:

.. code-block:: bash

    salt-cloud -m /etc/salt/saltify-map

This command will install salt on the machines specified in the map and will
give each machine their minion id of ``my-instance-0`` and ``my-instance-1``,
respectively. If the command was executed on the salt-master, its Salt key will
automatically be signed on the master.

Connectivity to the new "Salted" instances can now be verified with Salt:

.. code-block:: bash

    salt 'my-instance-*' test.version

Bulk Deployments
----------------

When deploying large numbers of Salt Minions using Saltify, it may be
preferable to organize the configuration in a way that duplicates data
as little as possible. For example, if a group of target systems have 
the same credentials, they can be specified in the profile, rather than
in a map file.

.. code-block:: yaml

    # /etc/salt/cloud.profiles.d/saltify.conf

    make_salty:
      provider: my-saltify-config
      ssh_username: root
      password: very-bad-password

.. code-block:: yaml

    # /etc/salt/saltify-map

    make_salty:
      - my-instance-0:
          ssh_host: 12.34.56.78
      - my-instance-1:
          ssh_host: 44.33.22.11

If ``ssh_host`` is not provided, its default value will be the Minion identifier
(``my-instance-0`` and ``my-instance-1``, in the example above). For deployments with
working DNS resolution, this can save a lot of redundant data in the map. Here is an
example map file using DNS names instead of IP addresses:

.. code-block:: yaml

    # /etc/salt/saltify-map

    make_salty:
      - my-instance-0
      - my-instance-1

Credential Verification
=======================

Because the Saltify driver does not actually create VM's, unlike other
salt-cloud drivers, it has special behaviour when the ``deploy`` option is set
to ``False``. When the cloud configuration specifies ``deploy: False``, the
Saltify driver will attempt to authenticate to the target node(s) and return
``True`` for each one that succeeds. This can be useful to verify ports,
protocols, services and credentials are correctly configured before a live
deployment.

Return values:
  - ``True``: Credential verification succeeded
  - ``False``: Credential verification succeeded
  - ``None``: Credential verification was not attempted.
