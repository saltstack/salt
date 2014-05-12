.. _acl-eauth:

==============================
External Authentication System
==============================

Salt's External Authentication System (eAuth) allows for Salt to  pass through
command authorization to any external authentication system, such as PAM or LDAP.

.. toctree::

    access_control

The external authentication system allows for specific users to be granted
access to execute specific functions on specific minions. Access is configured
in the master configuration file and uses the :ref:`access control system
<acl>`:

.. code-block:: yaml

    external_auth:
      pam:
        thatch:
          - 'web*':
            - test.*
            - network.*
        steve:
          - .*

The above configuration allows the user ``thatch`` to execute functions
in the test and network modules on the minions that match the web* target.
User ``steve`` is given unrestricted access to minion commands.

.. note:: The PAM module does not allow authenticating as ``root``.

To allow access to :ref:`wheel modules <all-salt.wheel>` or :ref:`runner
modules <all-salt.runners>` the following ``@`` syntax must be used:

.. code-block:: yaml

    external_auth:
      pam:
        thatch:
          - '@wheel'
          - '@runner'

The external authentication system can then be used from the command-line by
any user on the same system as the master with the ``-a`` option:

.. code-block:: bash

    $ salt -a pam web\* test.ping

The system will ask the user for the credentials required by the
authentication system and then publish the command.

To apply permissions to a group of users in an external authentication system,
append a ``%`` to the ID:

.. code-block:: yaml

    external_auth:
      pam:
        admins%:
          - '*':
            - 'pkg.*'

Tokens
------

With external authentication alone, the authentication credentials will be
required with every call to Salt. This can be alleviated with Salt tokens.

Tokens are short term authorizations and can be easily created by just
adding a ``-T`` option when authenticating:

.. code-block:: bash

    $ salt -T -a pam web\* test.ping

Now a token will be created that has a expiration of 12 hours (by default).
This token is stored in a file named ``.salt_token`` in the active user's home 
directory.

Once the token is created, it is sent with all subsequent communications.
User authentication does not need to be entered again until the token expires.

Token expiration time can be set in the Salt master config file.


LDAP 
----

Salt supports both user and group authentication for LDAP.

LDAP configuration happens in the Salt master configuration file.

Server configuration values:

.. code-block:: yaml

    auth.ldap.server: localhost
    auth.ldap.port: 389
    auth.ldap.tls: False
    auth.ldap.scope: 2

Salt also needs to know which Base DN to search for users and groups and
the DN to bind to:

.. code-block:: yaml

    auth.ldap.basedn: dc=saltstack,dc=com
    auth.ldap.binddn: cn=admin,dc=saltstack,dc=com

To bind to a DN, a password is required

.. code-block:: yaml

    auth.ldap.bindpw: mypassword

Salt users a filter to find the DN associated with a user. Salt substitutes
the ``{{ username }}`` value for the username when querying LDAP.

.. code-block:: yaml

    auth.ldap.filter: uid={{ username }}

If group support for LDAP is desired, one can specify an OU that contains group
data. This is prepended to the basedn to create a search path

.. code-block:: yaml

    auth.ldap.groupou: Groups

Once configured, LDAP permissions can be assigned to users and groups.

.. code-block:: yaml

    external_auth:
      ldap:
        test_ldap_user:
          - '*':
            - test.ping

To configure an LDAP group, append a ``%`` to the ID:

.. code-block:: yaml

    external_auth:
    ldap:
        test_ldap_group%:
          - '*':
            - test.echo
