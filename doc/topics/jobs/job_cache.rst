.. _managing_the_job_cache:

======================
Managing the Job Cache
======================

The Salt Master maintains a job cache of all job executions which can be
queried via the jobs runner. This job cache is called the Default Job Cache.

.. _default_job_cache:

Default Job Cache
=================

A number of options are available when configuring the job cache. The default
caching system uses local storage on the Salt Master and can be found in the
job cache directory (on Linux systems this is typically
``/var/cache/salt/master/jobs``). The default caching system is suitable for most
deployments as it does not typically require any further configuration or
management.

The default job cache is a temporary cache and jobs will be stored for 24
hours. If the default cache needs to store jobs for a different period the
time can be easily adjusted by changing the `keep_jobs` parameter in the
Salt Master configuration file. The value passed in is measured via hours:


.. code-block:: yaml

    keep_jobs: 24

Reducing the Size of the Default Job Cache
------------------------------------------

The Default Job Cache can sometimes be a burden on larger deployments (over 5000
minions). Disabling the job cache will make previously executed jobs unavailable
to the jobs system and is not generally recommended. Normally it is wise to make
sure the master has access to a faster IO system or a tmpfs is mounted to the
jobs dir.

However, you can disable the :conf_master:`job_cache` by setting it to ``False``
in the Salt Master configuration file. Setting this value to ``False`` means that
the Salt Master will no longer cache minion returns, but a JID directory and ``jid``
file for each job will still be created. This JID directory is necessary for
checking for and preventing JID collisions.

The default location for the job cache is in the ``/var/cache/salt/master/jobs/``
directory.

Setting the :conf_master:`job_cache`` to ``False`` in addition to setting
the :conf_master:`keep_jobs` option to a smaller value, such as ``1``, in the Salt
Master configuration file will reduce the size of the Default Job Cache, and thus
the burden on the Salt Master.

.. note::

    Changing the ``keep_jobs`` option sets the number of hours to keep old job
    information and defaults to ``24`` hours. Do not set this value to ``0`` when
    trying to make the cache cleaner run more frequently, as this means the cache
    cleaner will never run.


Additional Job Cache Options
============================

Many deployments may wish to use an external database to maintain a long term
register of executed jobs. Salt comes with two main mechanisms to do this, the
master job cache and the external job cache.

See :ref:`Storing Job Results in an External System <external-job-cache>`.


