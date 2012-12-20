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
in the master configuration file, and uses the new access control system:

.. code-block:: yaml

    external_auth:
      pam:
        thatch:
          - 'web*':
            - test.*
            - network.*

So, the above allows the user thatch to execute functions in the test and
network modules on the minions that match the web* target.

The external authentication system can then be used from the command line by
any user on the same system as the master with the `-a` option:

.. code-block:: bash

    $ salt -a pam web\* test.ping

The system will ask the user for the credentials required buy the
authentication system and then publish the command.

Tokens
------

With external authentication alone the authentication credentials will be
required with every call to Salt. This can be alleviated with Salt tokens.

The tokens are short term authorizations and can be easily created by just
adding a capital T option when authenticating:

.. code-block:: bash

    $ salt -T -a pam web\* test.ping

Now a token will be created that has a expiration of, by default, 12 hours.
This token is stored in the active user's home directory and is now sent with
all subsequent communications, so the authentication does not need to be 
declared again until the token expires.
