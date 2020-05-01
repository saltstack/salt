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

State Execution Module
======================

The :mod:`state.test <salt.modules.state.test>` function
can be used to test a state on a minion. This works by executing the
:mod:`state.apply <salt.modules.state.apply>` function while forcing the ``test`` kwarg
to ``True`` so that the ``state.apply`` function is not required to be called by the
user directly. This also allows you to add the ``state.test`` function to a minion's
``minion_blackout_whitelist`` pillar if you wish to be able to test a state while a
minion is in blackout.

New Grains
==========

systempath
----------

This grain provides the same information as the ``path`` grain, only formatted
as a list of directories.


Salt-SSH updates
================

ssh_pre_flight
--------------

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

set_path
--------

A new salt-ssh roster option `set_path` has been added. This allows you to set
the path environment variable used to run the salt-ssh command on the target minion.
You can set this setting in your roster file like so:

.. code-block:: yaml

  minion1:
    host: localhost
    user: root
    passwd: P@ssword
    set_path: '$PATH:/usr/local/bin/'


State Changes
=============
- Adding a new option for the State compiler, ``disabled_requisites`` will allow
  requisites to be disabled during State runs.


Salt Renderer updates
=====================

A new renderer for toml files has been added.

.. code-block:: none

  #!jinja|toml

  {% set myvar = "sometext" %}

  [["some id"."test.nop"]]
  name = "{{ myvar }}"
  [["some id"."test.nop"]]
  txt = "hello"
  [["some id"."test.nop"]]
  "somekey" = "somevalue"

Execution Module updates
========================

Vault Module
------------

The :py:func:`vault module <salt.modules.vault>` has been updated with the ability
to cache generated tokens. By specifying ``ttl`` or ``uses`` the token generated on
behalf of the minion will be allowed to persist and function for the defined time period
or number of uses.

.. code-block:: yaml

  vault:
    auth:
      uses: 25
