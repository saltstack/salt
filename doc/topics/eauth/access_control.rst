.. _acl:

=====================
Access Control System
=====================

.. versionadded:: 0.10.4

Salt maintains a standard system used to open granular control to non
administrative users to execute Salt commands. The access control system
has been applied to all systems used to configure access to non administrative
control interfaces in Salt.

These interfaces include, the ``peer`` system, the
``external auth`` system and the ``publisher acl`` system.

The access control system mandated a standard configuration syntax used in
all of the three aforementioned systems. While this adds functionality to the
configuration in 0.10.4, it does not negate the old configuration.

Now specific functions can be opened up to specific minions from specific users
in the case of external auth and publisher ACLs, and for specific minions in the
case of the peer system.

.. toctree::

    ../../ref/publisheracl
    index
    ../../ref/peer

.. The two paragraphs below (in the "When to use each authentication system"
   heading) are copied in the doc/ref/publisheracl.rst and doc/topics/eauth/index.rst
   topics as a note, at the top of the document. If you update the below
   content, update it in the other two files as well.

.. _acl_types:

When to Use Each Authentication System
======================================
``publisher_acl`` is useful for allowing local system users to run Salt
commands without giving them root access. If you can log into the Salt
master directly, then ``publisher_acl`` allows you to use Salt without
root privileges. If the local system is configured to authenticate against
a remote system, like LDAP or Active Directory, then ``publisher_acl`` will
interact with the remote system transparently.

``external_auth`` is useful for ``salt-api`` or for making your own scripts
that use Salt's Python API. It can be used at the CLI (with the ``-a``
flag) but it is more cumbersome as there are more steps involved.  The only
time it is useful at the CLI is when the local system is *not* configured
to authenticate against an external service *but* you still want Salt to
authenticate against an external service.

Examples
========

The access controls are manifested using matchers in these configurations:

.. code-block:: yaml

    publisher_acl:
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
          - test.version
          - mongo\*:
            - network.*
          - log\*:
            - network.*
            - pkg.*
          - 'G@os:RedHat':
            - kmod.*
        steve:
          - .*

The above allows for all minions to be hit by test.version by dave, and adds a
few functions that dave can execute on other minions. It also allows steve
unrestricted access to salt commands.

.. note::
    Functions are matched using regular expressions.
