=================
Client ACL system
=================

The salt client ACL system is a means to allow system users other than root to
have access to execute select salt commands on minions from the master.

The client ACL system is configured in the master configuration file via the
``client_acl`` configuration option. Under the ``client_acl`` configuration
option the users open to send commands are specified and then a list of regular
expressions which specify the minion functions which will be made available to
specified user. This configuration is much like the ``peer`` configuration:

.. code-block:: yaml

    client_acl:
      # Allow thatch to execute anything.
      thatch:
        - .*
      # Allow fred to use test and pkg, but only on "web*" minions.
      fred:
        - web*:
          - test.*
          - pkg.*

Permission Issues
=================

Directories required for ``client_acl`` must be modified to be readable by the
users specified:

.. code-block:: bash

    chmod 755 /var/cache/salt /var/cache/salt/master /var/cache/salt/master/jobs /var/run/salt /var/run/salt/master

.. note::

    In addition to the changes above you will also need to modify the
    permissions of /var/log/salt and the existing log file to be writable by
    the user(s) which will be running the commands. If you do not wish to do
    this then you must disable logging or Salt will generate errors as it
    cannot write to the logs as the system users.

If you are upgrading from earlier versions of salt you must also remove any
existing user keys and re-start the Salt master:

.. code-block:: bash

    rm /var/cache/salt/.*key
    service salt-master restart
