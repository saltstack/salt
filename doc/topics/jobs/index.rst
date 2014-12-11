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

Before finding a historic job, it may be required to find the job id. list_jobs
will parse the cached execution data and display all of the job data for jobs
that have already, or partially returned.

.. code-block:: bash

    # salt-run jobs.list_jobs

:index:`Scheduling Jobs`
========================
.. include:: schedule.rst

.. toctree::
    :hidden:

    schedule