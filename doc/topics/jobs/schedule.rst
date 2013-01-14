================
Salt Scheduleing
================

Introduced in Salt 0.12.0, the scheduling system is a powerful tool for
creating incremental executions on minions or the master. The schedule system
exposes the execution of any execution function on minions or any runner on
the master.

To set up the scheduler on the master add the schedule option to the master
config file, to set up the scheduler on the minion add the schedule option to
the minion config file or to the minion's pillar.

The schedule option defines jobs which execute at certain intervals. The salt
scheduler only supports interval assignments in 0.12.0. To set up a highstate
to run on a minion every 60 minutes set this in the minion config or pillar:

.. code-block:: yaml

    schedule:
      highstate:
        function: state.highstate
        minutes: 60

Time intervals can be specified as seconds, minutes, hours, or days. Runner
executions can also be specified on the master within the master configuration
file:

.. code-block:: yaml

    schedule:
      overstate:
        function: state.over
        seconds: 35
        minutes: 30
        hours: 3

The above configuration will execute the state.over runner every 3 hours,
30 minutes and 35 seconds, or every 12,635 seconds.

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
`schedule_returner` option is available to specify one or a list of global
returners to be used by the minions when scheduling.
