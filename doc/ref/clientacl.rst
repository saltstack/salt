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

Directories required for ``client_acl`` must be modified to be readable by the
users specified:

.. code-block:: bash

    chmod 755 /var/cache/salt /var/cache/salt/jobs /var/run/salt

If you are upgrading from earlier versions of salt you must also remove any
existing user keys and re-start the Salt master:

.. code-block:: bash

    rm /var/cache/salt/.*key
    service salt-master restart
