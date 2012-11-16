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
in the case of external auth and client acls, and for specific minions in the
case of the peer system.

The access controls are manifest using matchers in these configurations:

.. code-block:: yaml

    client_acl:
      fred:
        - web\*:
          - pkg.list_pkgs
          - test.*
          - apache.*

In the above example, fred is able to send commands only to minions which match
the specifieed glob target. This can be expanded to include other functions for
other minions based on standard targets.

.. code-block:: yaml

    external_auth:
      pam:
        dave:
          - mongo\*:
            - network.*
          - log\*:
            - network.*
            - pkg.*
          - 'G@os:RedHat':
            - kmod.*
          - test.ping

The above allows for all minions to be hit by test.ping by dave, and adds a
few functions for hitting other minions.
