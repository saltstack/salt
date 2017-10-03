.. _getting-started-with-saltify:

============================
Getting Started With Saltify
============================

The Saltify driver is a new, experimental driver for installing Salt on existing
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
      provider: saltify

However, if you wish to use the more advanced capabilities of salt-cloud, such as
rebooting, listing, and disconnecting machines, then the salt master must fill
the role usually performed by a vendor's cloud management system. In order to do
that, you must configure your salt master as a salt-api server, and supply credentials
to use it. (See ``salt-api setup`` below.)


Profiles
========

Saltify requires a profile to be configured for each machine that needs Salt
installed. The initial profile can be set up at ``/etc/salt/cloud.profiles``
or in the ``/etc/salt/cloud.profiles.d/`` directory. Each profile requires
both an ``ssh_host`` and an ``ssh_username`` key parameter as well as either
an ``key_filename`` or a ``password``.

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
key will automatically be signed on the master.

Once a salt-minion has been successfully installed on the instance, connectivity
to it can be verified with Salt:

.. code-block:: bash

    salt my-machine test.ping


Destroy Options
---------------

For obvious reasons, the ``destroy`` action does not actually vaporize hardware.
If the salt  master is connected using salt-api, it can tear down parts of
the client machines.  It will remove the client's key from the salt master,
and will attempt the following options:

.. code-block:: yaml

  - remove_config_on_destroy: true
    # default: true
    # Deactivate salt-minion on reboot and
    # delete the minion config and key files from its ``/etc/salt`` directory,
    #   NOTE: If deactivation is unsuccessful (older Ubuntu machines) then when
    #   salt-minion restarts it will automatically create a new, unwanted, set
    #   of key files. The ``force_minion_config`` option must be used in that case.

  - shutdown_on_destroy: false
    # default: false
    # send a ``shutdown`` command to the client.

.. versionadded:: Oxygen

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

    salt 'my-instance-*' test.ping

Credential Verification
=======================

Because the Saltify driver does not actually create VM's, unlike other
salt-cloud drivers, it has special behaviour when the ``deploy`` option is set
to ``False``. When the cloud configuration specifies ``deploy: False``, the
Saltify driver will attept to authenticate to the target node(s) and return
``True`` for each one that succeeds. This can be useful to verify ports,
protocols, services and credentials are correctly configured before a live
deployment.

Return values:
  - ``True``: Credential verification succeeded
  - ``False``: Credential verification succeeded
  - ``None``: Credential verification was not attempted.

Provisioning salt-api
=====================

In order to query or control minions it created, saltify needs to send commands
to the salt master.  It does that using the network interface to salt-api.

The salt-api is not enabled by default. The following example will provide a
simple installation.

.. code-block:: yaml

    # file /etc/salt/cloud.profiles.d/my_saltify_profiles.conf
    hw_41:  # a theoretical example hardware machine
      ssh_host: 10.100.9.41  # the hard address of your target
      ssh_username: vagrant  # a user name which has passwordless sudo
      password: vagrant      # on your target machine
      provider: my_saltify_provider


.. code-block:: yaml

    # file /etc/salt/cloud.providers.d/saltify_provider.conf
    my_saltify_provider:
      driver: saltify
      eauth: pam
      username: vagrant  # supply some sudo-group-member's name
      password: vagrant  # and password on the salt master
      minion:
        master: 10.100.9.5  # the hard address of the master


.. code-block:: yaml

    # file /etc/salt/master.d/auth.conf
    #  using salt-api ... members of the 'sudo' group can do anything ...
    external_auth:
      pam:
        sudo%:
          - .*
          - '@wheel'
          - '@runner'
          - '@jobs'


.. code-block:: yaml

    # file /etc/salt/master.d/api.conf
    # see https://docs.saltstack.com/en/latest/ref/netapi/all/salt.netapi.rest_cherrypy.html
    rest_cherrypy:
      host: localhost
      port: 8000
      ssl_crt: /etc/pki/tls/certs/localhost.crt
      ssl_key: /etc/pki/tls/certs/localhost.key
      thread_pool: 30
      socket_queue_size: 10


Start your target machine as a Salt minion named "node41" by:

.. code-block:: bash

    $ sudo salt-cloud -p hw_41 node41

