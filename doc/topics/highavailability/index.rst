.. _highavailability:

==================================
High Availability Features in Salt
==================================

Salt supports several features for high availability and fault tolerance.
Brief documentation for these features is listed alongside their configuration
parameters in :ref:`Configuration file examples <configuration-file-examples>`.

Multimaster
===========

Salt minions can connect to multiple masters at one time by configuring the
`master` configuration parameter as a YAML list of all the available masters.  By
default, all masters are "hot", meaning that any master can direct commands to
the Salt infrastructure.

In a multimaster configuration, each master must have the same cryptographic
keys, and minion keys must be accepted on all masters separately.  The contents
of file_roots and pillar_roots need to be kept in sync with processes external
to Salt as well

A tutorial on setting up multimaster with "hot" masters is here:

:ref:`Multimaster Tutorial <tutorial-multi-master>`

Multimaster with Failover
=========================

Changing the ``master_type`` parameter from ``str`` to ``failover`` will cause
minions to connect to the first responding master in the list of masters. Every
:conf_minion:`master_alive_interval` seconds the minions will check to make
sure the current master is still responding.  If the master does not respond,
the minion will attempt to connect to the next master in the list.  If the
minion runs out of masters, the list will be recycled in case dead masters have
been restored.  Note that :conf_minion:`master_alive_interval` must be present
in the minion configuration, or else the recurring job to check master status
will not get scheduled.

Failover can be combined with PKI-style encrypted keys, but PKI is NOT
REQUIRED to use failover.

Multimaster with PKI and Failover is discussed in
:ref:`this tutorial <tutorial-multi-master-pki>`

``master_type: failover`` can be combined with ``master_shuffle: True``
to spread minion connections across all masters (one master per
minion, not each minion connecting to all masters).  Adding Salt Syndics
into the mix makes it possible to create a load-balanced Salt infrastructure.
If a master fails, minions will notice and select another master from the
available list.

Syndic
======

Salt's Syndic feature is a way to create differing infrastructure
topologies.  It is not strictly an HA feature, but can be treated as such.

With the syndic, a Salt infrastructure can be partitioned in such a way that
certain masters control certain segments of the infrastructure, and "Master
of Masters" nodes can control multiple segments underneath them.

Syndics are covered in depth in :ref:`Salt Syndic <syndic>`.

Syndic with Multimaster
=======================

.. versionadded:: 2015.5.0

Syndic with Multimaster lets you connect a syndic to multiple masters to provide
an additional layer of redundancy in a syndic configuration.

Syndics are covered in depth in :ref:`Salt Syndic <syndic>`.
