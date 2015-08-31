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

Because the Saltify driver does not use an actual cloud provider host, it has a
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
