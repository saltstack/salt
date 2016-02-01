.. _acl-eauth:

==============================
External Authentication System
==============================

Salt's External Authentication System (eAuth) allows for Salt to pass through
command authorization to any external authentication system, such as PAM or LDAP.

.. note::

    eAuth using the PAM external auth system requires salt-master to be run as
    root as this system needs root access to check authentication.

External Authentication System Configuration
============================================
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

Salt respects the current PAM configuration in place, and uses the 'login'
service to authenticate.

.. note:: The PAM module does not allow authenticating as ``root``.

.. note:: state.sls and state.highstate will return "Failed to authenticate!"
   if the request timeout is reached.  Use -t flag to increase the timeout

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

Now a token will be created that has an expiration of 12 hours (by default).
This token is stored in a file named ``salt_token`` in the active user's home
directory.

Once the token is created, it is sent with all subsequent communications.
User authentication does not need to be entered again until the token expires.

Token expiration time can be set in the Salt master config file.


LDAP and Active Directory
=========================
.. note::

    LDAP usage requires that you have installed python-ldap.

Salt supports both user and group authentication for LDAP (and Active Directory
accessed via its LDAP interface)

OpenLDAP and similar systems
----------------------------
LDAP configuration happens in the Salt master configuration file.

Server configuration values and their defaults:

.. code-block:: yaml

    # Server to auth against
    auth.ldap.server: localhost

    # Port to connect via
    auth.ldap.port: 389

    # Use TLS when connecting
    auth.ldap.tls: False

    # LDAP scope level, almost always 2
    auth.ldap.scope: 2

    # Server specified in URI format
    auth.ldap.uri: ''    # Overrides .ldap.server, .ldap.port, .ldap.tls above

    # Verify server's TLS certificate
    auth.ldap.no_verify: False

    # Bind to LDAP anonymously to determine group membership
    # Active Directory does not allow anonymous binds without special configuration
    auth.ldap.anonymous: False

    # FOR TESTING ONLY, this is a VERY insecure setting.
    # If this is True, the LDAP bind password will be ignored and
    # access will be determined by group membership alone with
    # the group memberships being retrieved via anonymous bind
    auth.ldap.auth_by_group_membership_only: False

    # Require authenticating user to be part of this Organizational Unit
    # This can be blank if your LDAP schema does not use this kind of OU
    auth.ldap.groupou: 'Groups'

    # Object Class for groups.  An LDAP search will be done to find all groups of this
    # class to which the authenticating user belongs.
    auth.ldap.groupclass: 'posixGroup'

    # Unique ID attribute name for the user
    auth.ldap.accountattributename: 'memberUid'

    # These are only for Active Directory
    auth.ldap.activedirectory: False
    auth.ldap.persontype: 'person'

There are two phases to LDAP authentication.  First, Salt authenticates to search for a users' Distinguished Name
and group membership.  The user it authenticates as in this phase is often a special LDAP system user with
read-only access to the LDAP directory.  After Salt searches the directory to determine the actual user's DN
and groups, it re-authenticates as the user running the Salt commands.

If you are already aware of the structure of your DNs and permissions in your LDAP store are set such that
users can look up their own group memberships, then the first and second users can be the same.  To tell Salt this is
the case, omit the ``auth.ldap.bindpw`` parameter.  You can template the ``binddn`` like this:

.. code-block:: yaml

    auth.ldap.basedn: dc=saltstack,dc=com
    auth.ldap.binddn: uid={{ username }},cn=users,cn=accounts,dc=saltstack,dc=com

Salt will use the password entered on the salt command line in place of the bindpw.

To use two separate users, specify the LDAP lookup user in the binddn directive, and include a bindpw like so

.. code-block:: yaml

    auth.ldap.binddn: uid=ldaplookup,cn=sysaccounts,cn=etc,dc=saltstack,dc=com
    auth.ldap.bindpw: mypassword

As mentioned before, Salt uses a filter to find the DN associated with a user. Salt
substitutes the ``{{ username }}`` value for the username when querying LDAP

.. code-block:: yaml

    auth.ldap.filter: uid={{ username }}

For OpenLDAP, to determine group membership, one can specify an OU that contains
group data. This is prepended to the basedn to create a search path.  Then
the results are filtered against ``auth.ldap.groupclass``, default
``posixGroup``, and the account's 'name' attribute, ``memberUid`` by default.

.. code-block:: yaml

    auth.ldap.groupou: Groups

Active Directory
----------------

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
the user belongs to, he or she is denied access. Next, the ``distinguishedName``
of the user is looked up with the following LDAP search:

.. code-block:: text

    (&(<value of auth.ldap.accountattributename>={{username}})
      (objectClass=<value of auth.ldap.persontype>)
    )

This should return a distinguishedName that we can use to filter for group
membership.  Then the following LDAP query is executed:

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

To configure a LDAP group, append a ``%`` to the ID:

.. code-block:: yaml

    external_auth:
      ldap:
        test_ldap_group%:
          - '*':
            - test.echo
