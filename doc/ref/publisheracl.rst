.. _publisher-acl:

====================
Publisher ACL system
====================

The salt publisher ACL system is a means to allow system users other than root
to have access to execute select salt commands on minions from the master.

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

The publisher ACL system is configured in the master configuration file via the
``publisher_acl`` configuration option. Under the ``publisher_acl``
configuration option the users open to send commands are specified and then a
list of the minion functions which will be made available to specified user.

Both users and functions are matched with regular expressions, not shell
globs. ``pkg.*`` therefore matches every function in the ``pkg`` module
*and* every function in ``pkg_resource``, ``pkgin``, ``pkgng``,
``pkgutil``, and any other module whose name starts with ``pkg``.
Anchor the match with ``^`` and ``$`` when this is not what you want
(``^pkg\..*$``).

Minion target matchers are still shell globs and behave like ``salt 'web*'``.

This configuration is much like the :ref:`external_auth <acl-eauth>`
configuration:

.. code-block:: yaml

    publisher_acl:
      # Allow thatch to execute anything.
      thatch:
        - .*
      # Allow fred to use any test and pkg function, but only on "web*"
      # minions.
      fred:
        - 'web*':
          - test.*
          - pkg.*
      # Allow admin and managers to use saltutil module functions
      admin|manager_.*:
        - saltutil.*
      # Allow users to use only my_mod functions on "web*" minions with
      # specific arguments.
      user_.*:
        - 'web*':
          - 'my_mod.*':
              args:
                - 'a.*'
                - 'b.*'
              kwargs:
                'kwa': 'kwa.*'
                'kwb': 'kwb'

.. warning::

    Granting ``cmd.*`` (or any other module that runs shell on the
    minion, such as ``cmd.run``, ``cmd.shell``, ``file.write``,
    ``state.single``, ``file.touch``, ``user.add``...) is effectively
    granting root on every targeted minion when the minion runs as
    root (the default). The publisher ACL system controls *which*
    function a user can dispatch, not what that function does once it
    runs. Restrict by module function; do not assume that an ACL row
    sandboxes the minion-side effect.

Runner, wheel, and jobs (``@runner``, ``@wheel``, ``@jobs``)
------------------------------------------------------------

The runner and wheel subsystems run on the master, not on a minion.
``publisher_acl`` accepts the same ``@<form>`` syntax as
:ref:`external_auth <acl-eauth>` to grant access to these. A glob
target does **not** grant runner or wheel access; the form must be
spelled out:

.. code-block:: yaml

    publisher_acl:
      ops_user:
        - '@wheel'    # any wheel module function
        - '@runner'   # any runner module function
        - '@jobs'     # the jobs runner / wheel
        - '@key'      # the wheel.key module only
        - '@manage'   # the runner.manage module only
        - '@key':     # narrow to specific wheel.key functions
          - accept
          - finger

The same argument and keyword-argument restrictions documented for
``external_auth`` :ref:`apply here <acl-eauth>`.

.. note::

    Granting ``@runner`` or ``@wheel`` to a non-root user gives that
    user master-side execution; the runner runs as the master user. A
    user with ``@runner`` can in particular invoke ``salt.cmd`` to
    re-publish as the master and bypass other ``publisher_acl`` rules.
    Treat ``@runner`` and ``@wheel`` as the master-side equivalent of
    ``cmd.run`` on a minion.

Permission Issues
-----------------
Directories required for ``publisher_acl`` must be modified to be readable by
the users specified:

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

Whitelist and Blacklist
-----------------------
Salt's authentication systems can be configured by specifying what is allowed
using a whitelist, or by specifying what is disallowed using a blacklist. If
you specify a whitelist, only specified operations are allowed. If you specify
a blacklist, all operations are allowed except those that are blacklisted.

See :conf_master:`publisher_acl` and :conf_master:`publisher_acl_blacklist`.
