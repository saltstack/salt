.. _acl-eauth:

==============================
External Authentication System
==============================

Salt 0.10.4 comes with a fantastic new way to open up running Salt commands
to users. This system allows for Salt itself to pass through authentication to
any authentication system (The Unix PAM system was the first) to determine
if a user has permission to execute a Salt command.

The external authentication system allows for specific users to be granted
access to execute specific functions on specific minions. Access is configured
in the master configuration file, and uses the new :ref:`access control system
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

So, the above allows the user thatch to execute functions in the test and
network modules on the minions that match the web* target. User steve is
given unrestricted access to minion commands.

.. note:: The PAM module does not allow authenticating as ``root``.

To allow access to :ref:`wheel modules <all-salt.wheel>` or :ref:`runner
modules <all-salt.runners>` the following ``@`` syntax must be used:

.. code-block:: yaml

    external_auth:
      pam:
        thatch:
          - '@wheel'
          - '@runner'

The external authentication system can then be used from the command line by
any user on the same system as the master with the `-a` option:

.. code-block:: bash

    $ salt -a pam web\* test.ping

The system will ask the user for the credentials required by the
authentication system and then publish the command.

Tokens
------

With external authentication alone the authentication credentials will be
required with every call to Salt. This can be alleviated with Salt tokens.

The tokens are short term authorizations and can be easily created by just
adding a ``-T`` option when authenticating:

.. code-block:: bash

    $ salt -T -a pam web\* test.ping

Now a token will be created that has a expiration of, by default, 12 hours.
This token is stored in a file named ``.salt_token`` in the active user's home 
directory. Once the token is created, it is sent with all subsequent communications.
The user authentication does not need to be entered again until the token expires. The
token expiration time can be set in the Salt master config file.
