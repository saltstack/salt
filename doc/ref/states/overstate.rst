================
OverState System
================

Often servers need to be set up and configured in a specific order, and systems
should only be set up if systems earlier in the sequence has been set up
without any issues.

The 0.11.0 release of Salt addresses this problem with a new layer in the state
system called the `Over State`. The concept of the `Over State` is managed on
the master, a series of state executions is controlled from the master and
executed in order. If an execution requires that another execution first run
without problems then the state executions will stop.

The `Over State` system is used to orchestrate deployment in a smooth and
reliable way across multiple systems in small to large environments.

The Over State SLS
==================

The overstate system is managed by an sls file located in the root of an
environment. This file uses a data structure like all sls files.

The overstate sls file configures an unordered list of stages, each stage
defines the minions to execute on and can define what sls files to run
or to execute a state.highstate.

.. code-block:: yaml

    mysql:
      match: db*
      sls:
        - mysql.server
        - drbd
    webservers:
      match: web*
      require:
        - mysql
    all:
      match: '*'
      require:
        - mysql
        - webservers

The above defined over state will execute the msql stage first because it is
required by the webservers stage. The webservers stage will then be executed
only if the mysql stage executes without any issues. The webservers stage
will execute state.highstate on the matched minions, while the mysql stage
will execute state.sls with the named sls files.

Finally the all stage will execute state.highstate on all systems only if the
mysql and webservers stages complete without issue.

Executing the Over State
========================

The over state can be executed from the salt-run command, calling the
state.over runner function. The function will by default look in the base
environment for the overstate.sls file:

.. code-block:: bash

    salt-run state.over

To specify the location of the overstate file and the environment to pull from
pass the arguments to the salt-run command:

.. code-block:: bash

    salt-run state.over base /root/overstate.sls

Remember, that these calls are made on the master.
