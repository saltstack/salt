================
Salt Scheduling
================

In Salt versions greater than 0.12.0, the scheduling system allows incremental 
executions on minions or the master. The schedule system exposes the execution 
of any execution function on minions or any runner on the master.

Scheduling is enabled via the ``schedule`` option on either the master or minion 
config files, or via a minion's pillar data.

.. note::

    The scheduler executes different functions on the master and minions. When
    running on the master the functions reference runner functions, when
    running on the minion the functions specify execution functions.

Specify ``maxrunning`` to ensure that there are no more than N copies of
a particular routine running.  Use this for jobs that may be long-running
and could step on each other or otherwise double execute.  The default for 
``maxrunning`` is 1.

States are executed on the minion, as all states are. You can pass positional
arguments are provide a yaml dict of named arguments.

States
======

.. code-block:: yaml

    schedule:
      log-loadavg:
        function: cmd.run
        seconds: 3660
        args:
          - 'logger -t salt < /proc/loadavg'
        kwargs:
          stateful: False
          shell: True

Highstates
==========

To set up a highstate to run on a minion every 60 minutes set this in the
minion config or pillar:

.. code-block:: yaml

    schedule:
      highstate:
        function: state.highstate
        minutes: 60

Time intervals can be specified as seconds, minutes, hours, or days. 

Runners
=======

Runner executions can also be specified on the master within the master 
configuration file:

.. code-block:: yaml

    schedule:
      overstate:
        function: state.over
        seconds: 35
        minutes: 30
        hours: 3

The above configuration will execute the state.over runner every 3 hours,
30 minutes and 35 seconds, or every 12,635 seconds.

Scheduler With Returner
=======================

The scheduler is also useful for tasks like gathering monitoring data about
a minion, this schedule option will gather status data and send it to a mysql
returner database:

.. code-block:: yaml

    schedule:
      uptime:
        function: status.uptime
        seconds: 60
        returner: mysql
      meminfo:
        function: status.meminfo
        minutes: 5
        returner: mysql
      
Since specifying the returner repeatedly can be tiresome, the
``schedule_returner`` option is available to specify one or a list of global
returners to be used by the minions when scheduling.
