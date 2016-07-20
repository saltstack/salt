.. _acl:

=====================
Access Control System
=====================

.. versionadded:: 0.10.4

Salt maintains a standard system used to open granular control to non
administrative users to execute Salt commands. The access control system
has been applied to all systems used to configure access to non administrative
control interfaces in Salt.These interfaces include, the ``peer`` system, the
``external auth`` system and the ``client acl`` system.

The access control system mandated a standard configuration syntax used in
all of the three aforementioned systems. While this adds functionality to the
configuration in 0.10.4, it does not negate the old configuration.

Now specific functions can be opened up to specific minions from specific users
in the case of external auth and client ACLs, and for specific minions in the
case of the peer system.

The access controls are manifested using matchers in these configurations:

.. code-block:: yaml

    client_acl:
      fred:
        - web\*:
          - pkg.list_pkgs
          - test.*
          - apache.*

In the above example, fred is able to send commands only to minions which match
the specified glob target. This can be expanded to include other functions for
other minions based on standard targets (all matchers are supported except the compound one).

.. code-block:: yaml

    external_auth:
      pam:
        dave:
          - test.ping
          - mongo\*:
            - network.*
          - log\*:
            - network.*
            - pkg.*
          - 'G@os:RedHat':
            - kmod.*
        steve:
          - .*


The above allows for all minions to be hit by test.ping by dave, and adds a
few functions that dave can execute on other minions. It also allows steve
unrestricted access to salt commands.

.. note::
    Functions are matched using regular expressions.
