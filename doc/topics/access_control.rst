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
case of 
