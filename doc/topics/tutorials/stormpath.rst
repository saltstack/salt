=========================
Using Salt with Stormpath
=========================

`Stormpath <https://stormpath.com/>`_ is a user management and authentication
service. This tutorial covers using SaltStack to manage and take advantage of
Stormpath's features.

External Authentication
-----------------------
Stormpath can be used for Salt's external authentication system. In order to do
this, the master should be configured with an ``apiid``, ``apikey``, and the ID
of the ``application`` that is associated with the users to be authenticated:

.. code-block:: yaml

    stormpath:
      apiid: 367DFSF4FRJ8767FSF4G34FGH
      apikey: FEFREF43t3FEFRe/f323fwer4FWF3445gferWRWEer1
      application: 786786FREFrefreg435fr1

.. note::
    These values can be found in the `Stormpath dashboard
    <https://api.stormpath.com/ui2/index.html#/>`_`.

Users that are to be authenticated should be set up under the ``stormpath``
dict under ``external_auth``:

.. code-block:: yaml

    external_auth:
      stormpath:
        larry:
          - .*
          - '@runner'
          - '@wheel'

Keep in mind that while Stormpath defaults the username associated with the
account to the email address, it is better to use a username without an ``@``
sign in it.


Configuring Stormpath Modules
-----------------------------
Stormpath accounts can be managed via either an execution or state module. In
order to use either, a minion must be configured with an API ID and key.

.. code-block:: yaml

    stormpath:
      apiid: 367DFSF4FRJ8767FSF4G34FGH
      apikey: FEFREF43t3FEFRe/f323fwer4FWF3445gferWRWEer1
      directory: efreg435fr1786786FREFr
      application: 786786FREFrefreg435fr1

Some functions in the ``stormpath`` modules can make use of other options. The
following options are also available.

directory
`````````
The ID of the directory that is to be used with this minion. Many functions
require an ID to be specified to do their work. However, if the ID of a
``directory`` is specified, then Salt can often look up the resource in
question.

application
```````````
The ID of the application that is to be used with this minion. Many functions
require an ID to be specified to do their work. However, if the ID of a
``application`` is specified, then Salt can often look up the resource in
question.


Managing Stormpath Accounts
---------------------------
With the ``stormpath`` configuration in place, Salt can be used to configure
accounts (which may be thought of as users) on the Stormpath service. The
following functions are available.

stormpath.create_account
````````````````````````
Create an account on the Stormpath service. This requires a ``directory_id`` as
the first argument; it will not be retrieved from the minion configuration. An
``email`` address, ``password``, first name (``givenName``) and last name
(``surname``) are also required. For the full list of other parameters that may
be specified, see:

http://docs.stormpath.com/rest/product-guide/#account-resource

When executed with no errors, this function will return the information about
the account, from Stormpath.

.. code-block:: bash

    salt myminion stormpath.create_account <directory_id> shemp@example.com letmein Shemp Howard


stormpath.list_accounts
```````````````````````
Show all accounts on the Stormpath service. This will return all accounts,
regardless of directory, application, or group.

.. code-block:: bash

    salt myminion stormpath.list_accounts
    '''

stormpath.show_account
``````````````````````
Show the details for a specific Stormpath account. An ``account_id`` is normally
required. However, if am ``email`` is provided instead, along with either a
``directory_id``, ``application_id``, or ``group_id``, then Salt will search the
specified resource to try and locate the ``account_id``.

.. code-block:: bash

    salt myminion stormpath.show_account <account_id>
    salt myminion stormpath.show_account email=<email> directory_id=<directory_id>


stormpath.update_account
````````````````````````
Update one or more items for this account. Specifying an empty value will clear
it for that account. This function may be used in one of two ways. In order to
update only one key/value pair, specify them in order:

.. code-block:: bash

    salt myminion stormpath.update_account <account_id> givenName shemp
    salt myminion stormpath.update_account <account_id> middleName ''

In order to specify multiple items, they need to be passed in as a dict. From
the command line, it is best to do this as a JSON string:

.. code-block:: bash

    salt myminion stormpath.update_account <account_id> items='{"givenName": "Shemp"}
    salt myminion stormpath.update_account <account_id> items='{"middlename": ""}

When executed with no errors, this function will return the information about
the account, from Stormpath.


stormpath.delete_account
````````````````````````
Delete an account from Stormpath.

.. code-block:: bash

    salt myminion stormpath.delete_account <account_id>


stormpath.list_directories
``````````````````````````
Show all directories associated with this tenant.

.. code-block:: bash

    salt myminion stormpath.list_directories


Using Stormpath States
----------------------
Stormpath resources may be managed using the state system. The following states
are available.

stormpath_account.present
`````````````````````````
Ensure that an account exists on the Stormpath service. All options that are
available with the ``stormpath.create_account`` function are available here.
If an account needs to be created, then this function will require the same
fields that ``stormpath.create_account`` requires, including the ``password``.
However, if a password changes for an existing account, it will NOT be updated
by this state.

.. code-block:: bash

  curly@example.com:
    stormpath_account.present:
      - directory_id: efreg435fr1786786FREFr
      - password: badpass
      - firstName: Curly
      - surname: Howard
      - nickname: curly

It is advisable to always set a ``nickname`` that is not also an email address,
so that it can be used by Salt's external authentication module.

stormpath_account.absent
````````````````````````
Ensure that an account does not exist on Stormpath. As with
``stormpath_account.present``, the ``name`` supplied to this state is the
``email`` address associated with this account. Salt will use this, with or
without the ``directory`` ID that is configured for the minion. However, lookups
will be much faster with a directory ID specified.

