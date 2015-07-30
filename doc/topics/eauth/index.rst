.. _acl-eauth:

==============================
External Authentication System
==============================

Salt's External Authentication System (eAuth) allows for Salt to pass through
command authorization to any external authentication system, such as PAM or LDAP.

Access Control System
---------------------

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
          - '@wheel'   # to allow access to all wheel modules
          - '@runner'  # to allow access to all runner modules
          - '@jobs'    # to allow access to the jobs runner and/or wheel module

.. note::
    The runner/wheel markup is different, since there are no minions to scope the
    acl to.

.. note::
    Globs will not match wheel or runners! They must be explicitly
    allowed with @wheel or @runner.

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

.. warning::
    All users that have external authentication privileges are allowed to run
    :mod:`saltutil.findjob <salt.modules.saltutil.find_job>`. Be aware
    that this could inadvertently expose some data such as minion IDs.

.. _salt-token-generation:

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


LDAP and Active Directory
-------------------------

Salt supports both user and group authentication for LDAP (and Active Directory
accessed via its LDAP interface)

LDAP configuration happens in the Salt master configuration file.

Server configuration values and their defaults:

.. code-block:: yaml

    auth.ldap.server: localhost
    auth.ldap.port: 389
    auth.ldap.tls: False
    auth.ldap.scope: 2
    auth.ldap.uri: ''
    auth.ldap.tls: False
    auth.ldap.no_verify: False
    auth.ldap.anonymous: False
    auth.ldap.groupou: 'Groups'
    auth.ldap.groupclass: 'posixGroup'
    auth.ldap.accountattributename: 'memberUid'

    # These are only for Active Directory
    auth.ldap.activedirectory: False
    auth.ldap.persontype: 'person'

Salt also needs to know which Base DN to search for users and groups and
the DN to bind to:

.. code-block:: yaml

    auth.ldap.basedn: dc=saltstack,dc=com
    auth.ldap.binddn: cn=admin,dc=saltstack,dc=com

To bind to a DN, a password is required

.. code-block:: yaml

    auth.ldap.bindpw: mypassword

Salt uses a filter to find the DN associated with a user. Salt
substitutes the ``{{ username }}`` value for the username when querying LDAP

.. code-block:: yaml

    auth.ldap.filter: uid={{ username }}

For OpenLDAP, to determine group membership, one can specify an OU that contains
group data. This is prepended to the basedn to create a search path.  Then
the results are filtered against ``auth.ldap.groupclass``, default
``posixGroup``, and the account's 'name' attribute, ``memberUid`` by default.

.. code-block:: yaml

    auth.ldap.groupou: Groups

Active Directory handles group membership differently, and does not utilize the
``groupou`` configuration variable.  AD needs the following options in
the master config:

.. code-block:: yaml

    auth.ldap.activedirectory: True
    auth.ldap.filter: sAMAccountName={{username}}
    auth.ldap.accountattributename: sAMAccountName
    auth.ldap.groupclass: group
    auth.ldap.persontype: person

To determine group membership in AD, the username and password that is entered
when LDAP is requested as the eAuth mechanism on the command line is used to
bind to AD's LDAP interface. If this fails, then it doesn't matter what groups
the user belongs to, he or she is denied access. Next, the distinguishedName
of the user is looked up with the following LDAP search:

.. code-block:: text

    (&(<value of auth.ldap.accountattributename>={{username}})
      (objectClass=<value of auth.ldap.persontype>)
    )

This should return a distinguishedName that we can use to filter for group
membership. Then the following LDAP query is executed:

.. code-block:: text

    (&(member=<distinguishedName from search above>)
      (objectClass=<value of auth.ldap.groupclass>)
    )


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
