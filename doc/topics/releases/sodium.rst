:orphan:

====================================
Salt Release Notes - Codename Sodium
====================================


Salt mine updates
=================

Syntax update
-------------

The syntax for defining salt functions in config or pillar files has changed to
also support the syntax used in :py:mod:`module.run <salt.states.module.run>`.
The old syntax for the mine_function - as a dict, or as a list with dicts that
contain more than exactly one key - is still supported but discouraged in favor
of the more uniform syntax of module.run.

State updates
=============

The ``creates`` state requisite has been migrated from the
:mod:`docker_container <salt.states.docker_container>` and :mod:`cmd <salt.states.cmd>`
states to become a global option. This acts similar to an equivalent
``unless: test -f filename`` but can also accept a list of filenames.

New Grains
==========

systempath
----------

This grain provides the same information as the ``path`` grain, only formatted
as a list of directories.


================
Salt-SSH updates
================

A new Salt-SSH roster option `ssh_pre_flight` has been added. This enables you to run a
script before Salt-SSH tries to run any commands. You can set this option in the roster
for a specific minion or use the `roster_defaults` to set it for all minions.

Example for setting `ssh_pre_flight` for specific host in roster file

.. code-block:: yaml

  minion1:
    host: localhost
    user: root
    passwd: P@ssword
    ssh_pre_flight: /srv/salt/pre_flight.sh

Example for setting `ssh_pre_flight` using roster_defaults, so all minions
run this script.

.. code-block:: yaml

  roster_defaults:
    ssh_pre_flight: /srv/salt/pre_flight.sh

The `ssh_pre_flight` script will only run if the thin dir is not currently on the
minion. If you want to force the script to run you have the following options:

* Wipe the thin dir on the targeted minion using the -w arg.
* Set ssh_run_pre_flight to True in the config.
* Run salt-ssh with the --pre-flight arg.
