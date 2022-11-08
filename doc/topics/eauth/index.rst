.. _acl-eauth:

==============================
External Authentication System
==============================

Salt's External Authentication System (eAuth) allows for Salt to pass through
command authorization to any external authentication system, such as PAM or LDAP.

.. note::

    eAuth using the PAM external auth system requires salt-master to be run as
    root as this system needs root access to check authentication.

.. note::

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

    For more information and examples, see :ref:`this Access Control System
    <acl_types>` section.

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
        steve|admin.*:
          - .*

The above configuration allows the user ``thatch`` to execute functions in the
test and network modules on the minions that match the web* target.  User
``steve`` and the users whose logins start with ``admin``, are granted
unrestricted access to minion commands.

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

.. warning::
    All users that have external authentication privileges are allowed to run
    :mod:`saltutil.findjob <salt.modules.saltutil.find_job>`. Be aware
    that this could inadvertently expose some data such as minion IDs.

Matching syntax
---------------

The structure of the ``external_auth`` dictionary can take the following
shapes. User and function matches are exact matches, shell glob patterns or
regular expressions; minion matches are compound targets.

By user:

.. code-block:: yaml

    external_auth:
      <eauth backend>:
        <user or group%>:
          - <regex to match function>

By user, by minion:

.. code-block:: yaml

    external_auth:
      <eauth backend>:
        <user or group%>:
          <minion compound target>:
            - <regex to match function>

By user, by runner/wheel:

.. code-block:: yaml

    external_auth:
      <eauth backend>:
        <user or group%>:
          <@runner or @wheel>:
            - <regex to match function>

By user, by runner+wheel module:

.. code-block:: yaml

    external_auth:
      <eauth backend>:
        <user or group%>:
          <@module_name>:
            - <regex to match function without module_name>

Groups
------

To apply permissions to a group of users in an external authentication system,
append a ``%`` to the ID:

.. code-block:: yaml

    external_auth:
      pam:
        admins%:
          - '*':
            - 'pkg.*'

Limiting by function arguments
------------------------------

Positional arguments or keyword arguments to functions can also be whitelisted.

.. versionadded:: 2016.3.0

.. code-block:: yaml

    external_auth:
      pam:
        my_user:
          - '*':
            - 'my_mod.*':
                args:
                  - 'a.*'
                  - 'b.*'
                kwargs:
                  'kwa': 'kwa.*'
                  'kwb': 'kwb'
          - '@runner':
            - 'runner_mod.*':
                args:
                - 'a.*'
                - 'b.*'
                kwargs:
                  'kwa': 'kwa.*'
                  'kwb': 'kwb'

The rules:

1. The arguments values are matched as regexp.
2. If arguments restrictions are specified the only matched are allowed.
3. If an argument isn't specified any value is allowed.
4. To skip an arg use "everything" regexp ``.*``. I.e. if ``arg0`` and ``arg2``
   should be limited but ``arg1`` and other arguments could have any value use:

   .. code-block:: yaml

       args:
         - 'value0'
         - '.*'
         - 'value2'

Usage
=====

The external authentication system can then be used from the command-line by
any user on the same system as the master with the ``-a`` option:

.. code-block:: bash

    $ salt -a pam web\* test.version

The system will ask the user for the credentials required by the
authentication system and then publish the command.

.. _salt-token-generation:

Tokens
------

With external authentication alone, the authentication credentials will be
required with every call to Salt. This can be alleviated with Salt tokens.

Tokens are short term authorizations and can be easily created by just
adding a ``-T`` option when authenticating:

.. code-block:: bash

    $ salt -T -a pam web\* test.version

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

    # Use STARTTLS when connecting
    auth.ldap.starttls: False

    # LDAP scope level, almost always 2
    auth.ldap.scope: 2

    # Server specified in URI format
    auth.ldap.uri: ''    # Overrides .ldap.server, .ldap.port, .ldap.tls above

    # Verify server's TLS certificate
    auth.ldap.no_verify: False

    # Bind to LDAP anonymously to determine group membership
    # Active Directory does not allow anonymous binds without special configuration
    # In addition, if auth.ldap.anonymous is True, empty bind passwords are not permitted.
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

    auth.ldap.minion_stripdomains: []

    # Redhat Identity Policy Audit
    auth.ldap.freeipa: False


Authenticating to the LDAP Server
+++++++++++++++++++++++++++++++++

There are two phases to LDAP authentication.  First, Salt authenticates to search for a users' Distinguished Name
and group membership.  The user it authenticates as in this phase is often a special LDAP system user with
read-only access to the LDAP directory.  After Salt searches the directory to determine the actual user's DN
and groups, it re-authenticates as the user running the Salt commands.

If you are already aware of the structure of your DNs and permissions in your LDAP store are set such that
users can look up their own group memberships, then the first and second users can be the same.  To tell Salt this is
the case, omit the ``auth.ldap.bindpw`` parameter.  Note this is not the same thing as using an anonymous bind.
Most LDAP servers will not permit anonymous bind, and as mentioned above, if `auth.ldap.anonymous` is False you
cannot use an empty password.

You can template the ``binddn`` like this:

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


Determining Group Memberships (OpenLDAP / non-Active Directory)
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

For OpenLDAP, to determine group membership, one can specify an OU that contains
group data. This is prepended to the basedn to create a search path.  Then
the results are filtered against ``auth.ldap.groupclass``, default
``posixGroup``, and the account's 'name' attribute, ``memberUid`` by default.

.. code-block:: yaml

    auth.ldap.groupou: Groups

Note that as of 2017.7, auth.ldap.groupclass can refer to either a groupclass or an objectClass.
For some LDAP servers (notably OpenLDAP without the ``memberOf`` overlay enabled) to determine group
membership we need to know both the ``objectClass`` and the ``memberUid`` attributes.  Usually for these
servers you will want a ``auth.ldap.groupclass`` of ``posixGroup`` and an ``auth.ldap.groupattribute`` of
``memberUid``.

LDAP servers with the ``memberOf`` overlay will have entries similar to ``auth.ldap.groupclass: person`` and
``auth.ldap.groupattribute: memberOf``.

When using the ``ldap('DC=domain,DC=com')`` eauth operator, sometimes the records returned
from LDAP or Active Directory have fully-qualified domain names attached, while minion IDs
instead are simple hostnames.  The parameter below allows the administrator to strip
off a certain set of domain names so the hostnames looked up in the directory service
can match the minion IDs.

.. code-block:: yaml

   auth.ldap.minion_stripdomains: ['.external.bigcorp.com', '.internal.bigcorp.com']


Determining Group Memberships (Active Directory)
++++++++++++++++++++++++++++++++++++++++++++++++

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

In addition, if there are a set of computers in the directory service that should
be part of the eAuth definition, they can be specified like this:

.. code-block:: yaml

    external_auth:
      ldap:
        test_ldap_group%:
          - ldap('DC=corp,DC=example,DC=com'):
            - test.echo

The string inside ``ldap()`` above is any valid LDAP/AD tree limiter.  ``OU=`` in
particular is permitted as long as it would return a list of computer objects.
