.. _jobs:

=======================
:index:`Job Management`
=======================

.. versionadded:: 0.9.7

Since Salt executes jobs running on many systems, Salt needs to be able to
manage jobs running on many systems.

The :index:`Minion proc System`
===============================

Salt Minions maintain a *proc* directory in the Salt ``cachedir``. The *proc*
directory maintains files named after the executed job ID. These files contain
the information about the current running jobs on the minion and allow for
jobs to be looked up. This is located in the *proc* directory under the
cachedir, with a default configuration it is under ``/var/cache/salt/proc``.

Functions in the saltutil Module
================================

Salt 0.9.7 introduced a few new functions to the
:doc:`saltutil</ref/modules/all/salt.modules.saltutil>` module for managing
jobs. These functions are:

1. ``running``
   Returns the data of all running jobs that are found in the *proc* directory.

2. ``find_job``
   Returns specific data about a certain job based on job id.

3. ``signal_job``
   Allows for a given jid to be sent a signal.

4. ``term_job``
   Sends a termination signal (SIGTERM, 15) to the process controlling the
   specified job.

5. ``kill_job``
   Sends a kill signal (SIGKILL, 9) to the process controlling the
   specified job.

These functions make up the core of the back end used to manage jobs at the
minion level.

The jobs Runner
===============

A convenience runner front end and reporting system has been added as well.
The jobs runner contains functions to make viewing data easier and cleaner.

The jobs runner contains a number of functions...

active
------

The active function runs saltutil.running on all minions and formats the
return data about all running jobs in a much more usable and compact format.
The active function will also compare jobs that have returned and jobs that
are still running, making it easier to see what systems have completed a job
and what systems are still being waited on.

.. code-block:: bash

    # salt-run jobs.active

lookup_jid
----------

When jobs are executed the return data is sent back to the master and cached.
By default it is cached for 24 hours, but this can be configured via the
``keep_jobs`` option in the master configuration.
Using the lookup_jid runner will display the same return data that the initial
job invocation with the salt command would display.

.. code-block:: bash

    # salt-run jobs.lookup_jid <job id number>

list_jobs
---------

Before finding a historic job, it may be required to find the job id. ``list_jobs``
will parse the cached execution data and display all of the job data for jobs
that have already, or partially returned.

.. code-block:: bash

    # salt-run jobs.list_jobs

.. _scheduling-jobs:

Scheduling Jobs
===============
Salt's scheduling system allows incremental executions on minions or the
master. The schedule system exposes the execution of any execution function on
minions or any runner on the master.

Scheduling is enabled via the ``schedule`` option on either the master or minion
config files, or via a minion's pillar data. Schedules that are implemented via
pillar data, only need to refresh the minion's pillar data, for example by using
``saltutil.refresh_pillar``. Schedules implemented in the master or minion config
have to restart the application in order for the schedule to be implemented.

.. note::

    The scheduler executes different functions on the master and minions. When
    running on the master the functions reference runner functions, when
    running on the minion the functions specify execution functions.

A scheduled run has no output on the minion unless the config is set to info level
or higher. Refer to :conf_minion:`minion-logging-settings`.

Specify ``maxrunning`` to ensure that there are no more than N copies of
a particular routine running.  Use this for jobs that may be long-running
and could step on each other or otherwise double execute.  The default for
``maxrunning`` is 1.

States are executed on the minion, as all states are. You can pass positional
arguments and provide a yaml dict of named arguments.

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True

This will schedule the command: state.sls httpd test=True every 3600 seconds
(every hour)

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True
        splay: 15

This will schedule the command: state.sls httpd test=True every 3600 seconds
(every hour) splaying the time between 0 and 15 seconds

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True
        splay:
          start: 10
          end: 15

This will schedule the command: state.sls httpd test=True every 3600 seconds
(every hour) splaying the time between 10 and 15 seconds

.. versionadded:: 2014.7.0

Frequency of jobs can also be specified using date strings supported by
the python dateutil library. This requires python-dateutil to be installed on
the minion.

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        args:
          - httpd
        kwargs:
          test: True
        when: 5:00pm

This will schedule the command: state.sls httpd test=True at 5:00pm minion
localtime.

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        args:
          - httpd
        kwargs:
          test: True
        when:
            - Monday 5:00pm
            - Tuesday 3:00pm
            - Wednesday 5:00pm
            - Thursday 3:00pm
            - Friday 5:00pm

This will schedule the command: state.sls httpd test=True at 5pm on Monday,
Wednesday, and Friday, and 3pm on Tuesday and Thursday.

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True
        range:
            start: 8:00am
            end: 5:00pm

This will schedule the command: state.sls httpd test=True every 3600 seconds
(every hour) between the hours of 8am and 5pm.  The range parameter must be a
dictionary with the date strings using the dateutil format. This requires
python-dateutil to be installed on the minion.

.. code-block:: yaml

    schedule:
      job1:
        function: pkg.install
        kwargs:
          pkgs: [{'bar': '>1.2.3'}]
          refresh: true
        once: '2016-01-07T14:30:00'

This will schedule the command pkg.install to be executed once at the specified
time. The schedule entry ``job1`` will not be removed after the job completes,
therefore use ``schedule.delete`` to manually remove it afterwards.

The default date format is ISO 8601 but can be overridden by also specifying the
``once_fmt`` option.

.. versionadded:: 2014.7.0

The scheduler also supports ensuring that there are no more than N copies of
a particular routine running.  Use this for jobs that may be long-running
and could step on each other or pile up in case of infrastructure outage.

The default for maxrunning is 1.

.. code-block:: yaml

    schedule:
      long_running_job:
          function: big_file_transfer
          jid_include: True

Scheduling States
-----------------

.. code-block:: yaml

    schedule:
      log-loadavg:
        function: cmd.run
        seconds: 3660
        args:
          - 'logger -t salt < /proc/loadavg'
        kwargs:
          stateful: False
          shell: /bin/sh

Scheduling Highstates
---------------------
To set up a highstate to run on a minion every 60 minutes set this in the
minion config or pillar:

.. code-block:: yaml

    schedule:
      highstate:
        function: state.highstate
        minutes: 60

Time intervals can be specified as seconds, minutes, hours, or days.

Scheduling Runners
------------------
Runner executions can also be specified on the master within the master
configuration file:

.. code-block:: yaml

    schedule:
      run_my_orch:
        function: state.orchestrate
        hours: 6
        splay: 600
        args:
          - orchestration.my_orch

The above configuration is analogous to running
``salt-run state.orch orchestration.my_orch`` every 6 hours.

Scheduler With Returner
-----------------------
The scheduler is also useful for tasks like gathering monitoring data about
a minion, this schedule option will gather status data and send it to a MySQL
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

