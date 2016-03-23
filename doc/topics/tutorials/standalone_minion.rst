.. _tutorial-standalone-minion:

=================
Standalone Minion
=================

Since the Salt minion contains such extensive functionality it can be useful
to run it standalone. A standalone minion can be used to do a number of
things:

- Use salt-call commands on a system without connectivity to a master
- Masterless States, run states entirely from files local to the minion

.. note::

    When running Salt in masterless mode, do not run the salt-minion daemon.
    Otherwise, it will attempt to connect to a master and fail. The salt-call
    command stands on its own and does not need the salt-minion daemon.

Telling Salt Call to Run Masterless
===================================

The salt-call command is used to run module functions locally on a minion
instead of executing them from the master. Normally the salt-call command
checks into the master to retrieve file server and pillar data, but when
running standalone salt-call needs to be instructed to not check the master for
this data. To instruct the minion to not look for a master when running
salt-call the :conf_minion:`file_client` configuration option needs to be set.
By default the :conf_minion:`file_client` is set to ``remote`` so that the
minion knows that file server and pillar data are to be gathered from the
master. When setting the :conf_minion:`file_client` option to ``local`` the
minion is configured to not gather this data from the master.

.. code-block:: yaml

    file_client: local

Now the salt-call command will not look for a master and will assume that the
local system has all of the file and pillar resources.



Running States Masterless
=========================

The state system can be easily run without a Salt master, with all needed files
local to the minion. To do this the minion configuration file needs to be set
up to know how to return file_roots information like the master. The file_roots
setting defaults to /srv/salt for the base environment just like on the master:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt

Now set up the Salt State Tree, top file, and SLS modules in the same way that
they would be set up on a master. Now, with the :conf_minion:`file_client`
option set to ``local`` and an available state tree then calls to functions in
the state module will use the information in the file_roots on the minion
instead of checking in with the master.

Remember that when creating a state tree on a minion there are no syntax or
path changes needed, SLS modules written to be used from a master do not need
to be modified in any way to work with a minion.

This makes it easy to "script" deployments with Salt states without having to
set up a master, and allows for these SLS modules to be easily moved into a
Salt master as the deployment grows.

The declared state can now be executed with:

.. code-block:: bash

    salt-call state.apply

Or the salt-call command can be executed with the ``--local`` flag, this makes
it unnecessary to change the configuration file:

.. code-block:: bash

    salt-call state.apply --local

External Pillars
================

:ref:`External pillars <external-pillars>` are supported when running in masterless mode.

