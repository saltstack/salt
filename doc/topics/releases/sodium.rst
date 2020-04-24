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

A new Salt-SSH roster option ``ssh_pre_flight`` has been added. This enables you to run a
script before Salt-SSH tries to run any commands. You can set this option in the roster
for a specific minion or use the ``roster_defaults`` to set it for all minions.

Example for setting ``ssh_pre_flight`` for specific host in roster file

.. code-block:: yaml

  minion1:
    host: localhost
    user: root
    passwd: P@ssword
    ssh_pre_flight: /srv/salt/pre_flight.sh

Example for setting ``ssh_pre_flight`` using roster_defaults, so all minions
run this script.

.. code-block:: yaml

  roster_defaults:
    ssh_pre_flight: /srv/salt/pre_flight.sh

The ``ssh_pre_flight`` script will only run if the thin dir is not currently on the
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


auto_detect
-----------

You can now auto detect the dependencies to be packed into the salt thin when using
the ``ssh_ext_alternatives`` feature.

.. code-block:: yaml

       ssh_ext_alternatives:
           2019.2:                     # Namespace, can be anything.
               py-version: [2, 7]      # Constraint to specific interpreter version
               path: /opt/2019.2/salt  # Main Salt installation directory.
               auto_detect: True       # Auto detect dependencies
               py_bin: /usr/bin/python2.7 # Python binary path used to auto detect dependencies

This new ``auto_detect`` option needs to be set to True in your ``ssh_ext_alternatives`` configuration.
Salt-ssh will attempt to auto detect the file paths required for the default dependencies to include
in the thin. If you have a dependency already set in your configuration, it will not attempt to auto
detect for that dependency.

You can also set the ``py_bin`` option to set the python binary to be used to auto detect the
dependencies. If ``py_bin`` is not set, it will attempt to use the major Python version set in
``py-version``. For example, if you set ``py-version`` to be ``[2, 7]`` it will attempt to find and
use the ``python2`` binary.

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
