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

When a minion is connected to more than one master in "hot" mode it sends
its job returns and events to every master it is connected to. This means
event-driven workflows (reactors, beacons, ``salt-run state.event``)
behave the same on each master, but you should be prepared for duplicate
returns and events appearing in tooling that aggregates across masters.

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

``master_type: failover`` can be combined with ``random_master: True``
to spread minion connections across all masters (one master per
minion, not each minion connecting to all masters).  Adding Salt Syndics
into the mix makes it possible to create a load-balanced Salt infrastructure.
If a master fails, minions will notice and select another master from the
available list.

Key signing in HA topologies
============================

When more than one master serves the same set of minions, you have two
choices for the master key material that minions will trust:

* **Share the master key pair across all masters.** This is the
  approach described in :ref:`Multi Master Tutorial
  <tutorial-multi-master>`. The ``master.pem`` / ``master.pub`` pair
  is identical on every master, so a minion sees the same public key
  no matter which master it talks to.
* **Sign each master's public key with a shared signing key.** This is
  the approach described in
  :ref:`Multi-Master-PKI Tutorial With Failover
  <tutorial-multi-master-pki>`. Each master keeps its own
  ``master.pem`` / ``master.pub`` and additionally holds the signing
  key pair (``master_sign.pem`` / ``master_sign.pub``). Minions are
  configured with ``verify_master_pubkey_sign: True`` and the
  ``master_sign.pub`` from the signing key pair, so they can verify
  any signed master public key.

The two approaches do **not** mix. If you set
``master_sign_pubkey: True`` on the masters and
``verify_master_pubkey_sign: True`` on the minions, the masters must
also have a consistent signing key pair (``master_sign.*``) across the
HA pool. The simplest, supported topologies are:

#. All masters share ``master.pem`` / ``master.pub``; key signing is
   left disabled (no ``master_sign_pubkey`` on any master, no
   ``verify_master_pubkey_sign`` on any minion).
#. Each master keeps a unique ``master.pem`` / ``master.pub`` but every
   master has the same ``master_sign.pem`` / ``master_sign.pub``; both
   ``master_sign_pubkey: True`` on every master and
   ``verify_master_pubkey_sign: True`` on every minion are required.

Mixing these (for example, signing on some masters and not others, or
using different signing key pairs on different masters) causes minions
to reject auth replies after they fail over to a master whose key they
cannot verify. See :ref:`Multi-Master-PKI Tutorial With Failover
<tutorial-multi-master-pki>` for the full configuration and verification
log walkthrough.

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
