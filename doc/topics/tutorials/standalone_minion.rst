.. _tutorial-standalone-minion:

=================
Standalone Minion
=================

A standalone (or *masterless*) Salt minion is a Salt minion installation
that is not connected to a Salt master and runs everything locally. The
same code paths that execute on a normal minion run on a standalone
minion; what changes is the source of configuration, state files, and
pillar data, all of which come from local paths instead of the master's
file server.

A standalone minion is useful for:

- Running configuration management on hosts that have no network path to
  a Salt master (air-gapped systems, build agents, kiosks, single-server
  environments).
- Bootstrapping a system from local SLS files before joining it to a
  master (or as part of an image build pipeline).
- Local testing and development of state, pillar, or formula code with
  fast feedback via ``salt-call --local`` against checked-out SLS trees.
- Triggering :ref:`reactor <reactor>` and :ref:`beacons <beacon>` flows
  on a host that does not publish events to a master.

How a standalone minion differs from a master-connected minion:

- **Targeting is implicit.** ``salt-call`` always operates on the local
  host. There is no ``salt`` CLI for fanning out to other minions because
  there is no master.
- **File and pillar roots are local.** ``file_roots`` and ``pillar_roots``
  on the minion point at directories on the local filesystem (typically
  ``/srv/salt`` and ``/srv/pillar``). The minion does not fetch SLS files
  over the wire.
- **External pillars still work.** :ref:`External pillars
  <external-pillars>` (for example, gitfs or vault) can still be
  configured on a standalone minion, as long as the minion can reach the
  external source.
- **No mine, no jobs, no events to the master.** Anything that requires a
  master — the mine, multi-minion targeting, master-side returners, the
  reactor that runs on the master — is unavailable. Local-only reactors
  and engines do work.

There are two practical ways to operate a standalone minion:

1. **No daemon, just ``salt-call --local``.** This is the simplest mode.
   You do not run the ``salt-minion`` service at all; you invoke
   ``salt-call --local <function>`` on demand. Use this when the host
   only needs to be configured during provisioning or on a manual cadence.
2. **Running ``salt-minion`` with no master.** When you want beacons,
   engines, schedules, or a local reactor running continuously without a
   master connection, set :conf_minion:`master_type` to ``disable`` so
   the daemon does not attempt to connect to a master.

.. note::

    By default the salt-minion daemon will attempt to connect to a master
    and fail. The salt-call command stands on its own and does not need
    the salt-minion daemon. As of version 2016.11.0 you can run the
    salt-minion daemon without a master connection by setting
    :conf_minion:`master_type` to ``disable``.



Minion Configuration
--------------------

Throughout this document there are several references to setting different
options to configure a masterless Minion. Salt Minions are easy to configure
via a configuration file that is located, by default, in ``/etc/salt/minion``.
Note, however, that on FreeBSD systems, the minion configuration file is located
in ``/usr/local/etc/salt/minion``.

You can learn more about minion configuration options in the
:ref:`Configuring the Salt Minion <configuration-salt-minion>` docs.


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
