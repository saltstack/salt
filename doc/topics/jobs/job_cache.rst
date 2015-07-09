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

Additional Job Cache Options
============================

Many deployments may wish to use an external database to maintain a long term
register of executed jobs. Salt comes with two main mechanisms to do this, the
master job cache and the external job cache.

See :ref:`Storing Job Results in an External System <external-master-cache>`.


