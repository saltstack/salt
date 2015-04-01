=======================
Managing the Job Cache
=======================

The Salt Master maintains a job cache of all job executions which can be
queried via the jobs runner. The way this job cache is managed is very
pluggable via Salt's underlying returner interface.

.. _default_job_cache:

Default Job Cache
=================

A number of options are available when configuring the job cache. The default
caching system uses local storage on the Salt Master and can be found in the
job cache directory (on Linux systems this is typically
/var/cache/salt/master/jobs). The default caching system is suitable for most
deployments as it does not typically require any further configuration or
management.

The default job cache is a temporary cache and jobs will be stored for 24
hours. If the default cache needs to store jobs for a different period the
time can be easily adjusted by changing the `keep_jobs` parameter in the
Salt Master configuration file. The value passed in is measured via hours:


.. code-block:: yaml

    keep_jobs: 24

External Job Cache Options
==========================

Many deployments may wish to use an external database to maintain a long term
register of executed jobs. Salt comes with two main mechanisms to do this, the
master job cache and the external job cache. The difference is how the external
data store is accessed.

.. _master_job_cache:

Master Job Cache
================

.. versionadded:: 2014.7

The master job cache setting makes the built in job cache on the master
modular. This system allows for the default cache to be swapped out by the Salt
returner system. To configure the master job cache, set up an external returner
database based on the instructions included with each returner and then simply
add the following configuration to the master configuration file:

.. code-block:: yaml

    master_job_cache: mysql

.. _external_job_cache:

External Job Cache
==================

The external job cache setting instructs the minions to directly contact the
data store. This scenario is helpful when the data store needs to be made
available to the minions. This can be an effective way to share historic data
across an infrastructure as data can be retrieved from the external job cache
via the ``ret`` execution module.

To configure the external job cache, set up a returner database in the manner
described in the specific returner documentation. Ensure that the returner
database is accessible from the minions, and set the `ext_job_cache` setting
in the master configuration file:

.. code-block:: yaml

    ext_job_cache: redis
