=================
Client ACL system
=================

The salt client acl system is a means to allow system users other than root to
have access to execute select salt commands on minions from the master.

The client acl system is configured in the master configuration file via the
``client_acl`` configuration option. Under the ``client_acl`` configuration
option the users open to send commands are specified and then a list of regular
expressions which specify the minion functions which will be made available to
specified user. This configuration is much like the ``peer`` configuration:

.. code-block:: yaml

    # Allow thatch to execute anything and allow fred to use ping and pkg
    client_acl:
      thatch:
        - .*
      fred:
        - ping.*
        - pkg.*

Permission Issues
=================

Earlier versions of salt set overly restrictive permissions on some of the
directories required for ``client_acl`` support. These directories will need
to be manually modified if upgrading from an earlier version.

.. code-block:: bash

    chmod 755 /var/cache/salt
    chmod 755 /var/cache/salt/jobs
    chmod 755 /tmp/.salt-unix
