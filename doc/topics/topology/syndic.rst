.. _syndic:

===========
Salt Syndic
===========

The most basic or typical Salt topology consists of a single Master node
controlling a group of Minion nodes.  An intermediate node type, called Syndic,
when used offers greater structural flexibility and scalability in the
construction of Salt topologies than topologies constructed only out of Master
and Minion node types.

A Syndic node can be thought of as a special passthrough Minion node.  A Syndic
node consists of a ``salt-syndic`` daemon and a ``salt-master`` daemon running
on the same system.  The ``salt-master`` daemon running on the Syndic node
controls a group of lower level Minion nodes and the ``salt-syndic`` daemon
connects higher level Master node, sometimes called a Master of Masters.

The ``salt-syndic`` daemon relays publications and events between the Master
node and the local ``salt-master`` daemon.  This gives the Master node control
over the Minion nodes attached to the ``salt-master`` daemon running on the
Syndic node.

Configuring the Syndic
======================

To setup a Salt Syndic you need to tell the Syndic node and its Master node
about each other.  If your Master node is located at ``10.10.0.1``, then your
configurations would be:

On the Syndic node:

.. code-block:: yaml

    # /etc/salt/master
    syndic_master: 10.10.0.1  # may be either an IP address or a hostname

.. code-block:: yaml

    # /etc/salt/minion

    # id is shared by the salt-syndic daemon and a possible salt-minion daemon
    # on the Syndic node
    id: my_syndic

On the Master node:

.. code-block:: yaml

    # /etc/salt/master
    order_masters: True

The :conf_master:`syndic_master` option tells the Syndic node where to find the
Master node in the same way that the :conf_minion:`master` option tells a
Minion node where to find a Master node.

The :conf_minion:`id` option is used by the ``salt-syndic`` daemon to identify
with the Master node and if unset will default to the hostname or IP address of
the Syndic just as with a Minion.

The :conf_master:`order_masters` option configures the Master node to send
extra information with its publications that is needed by Syndic nodes
connected directly to it.

.. note::

    Each Syndic must provide its own ``file_roots`` directory. Files will not
    be automatically transferred from the Master node.

Configuring the Syndic with Multimaster
=======================================

.. versionadded:: 2015.5.0

Syndic with Multimaster lets you connect a syndic to multiple masters to provide
an additional layer of redundancy in a syndic configuration.

Higher level masters should first be configured in a multimaster configuration.
See :ref:`Multimaster Tutorial <tutorial-multi-master>`.

On the syndic, the :conf_master:`syndic_master` option is populated with
a list of the higher level masters.

Since each syndic is connected to each master, jobs sent from any master are
forwarded to minions that are connected to each syndic. If the ``master_id`` value
is set in the master config on the higher level masters, job results are returned
to the master that originated the request in a best effort fashion. Events/jobs
without a ``master_id`` are returned to any available master.

Running the Syndic
==================

The ``salt-syndic`` daemon is a separate process that needs to be started in
addition to the ``salt-master`` daemon running on the Syndic node.  Starting
the ``salt-syndic`` daemon is the same as starting the other Salt daemons.

The Master node in many ways sees the Syndic as an ordinary Minion node.  In
particular, the Master will need to accept the Syndic's Minion key as it would
for any other Minion.

On the Syndic node:

.. code-block:: bash

    # salt-syndic
    or
    # service salt-syndic start

On the Master node:

.. code-block:: bash

    # salt-key -a my_syndic

The Master node will now be able to control the Minion nodes connected to the
Syndic.  Only the Syndic key will be listed in the Master node's key registry
but this also means that key activity between the Syndic's Minions and the
Syndic does not encumber the Master node.  In this way, the Syndic's key on the
Master node can be thought of as a placeholder for the keys of all the Minion
and Syndic nodes beneath it, giving the Master node a clear, high level
structural view on the Salt cluster.

On the Master node:

.. code-block:: bash

    # salt-key -L
    Accepted Keys:
    my_syndic
    Denied Keys:
    Unaccepted Keys:
    Rejected Keys:

    # salt '*' test.ping
    minion_1:
        True
    minion_2:
        True
    minion_4:
        True
    minion_3:
        True

Topology
========

A Master node (a node which is itself not a Syndic to another higher level
Master node) must run a ``salt-master`` daemon and optionally a ``salt-minion``
daemon.

A Syndic node must run ``salt-syndic`` and ``salt-master`` daemons and
optionally a ``salt-minion`` daemon.

A Minion node must run a ``salt-minion`` daemon.

When a ``salt-master`` daemon issues a command, it will be received by the
Syndic and Minion nodes directly connected to it.  A Minion node will process
the command in the way it ordinarily would.  On a Syndic node, the
``salt-syndic`` daemon will relay the command to the ``salt-master`` daemon
running on the Syndic node, which then propagates the command to the Minions
and Syndics connected to it.

When events and job return data are generated by ``salt-minion`` daemons, they
are aggregated by the ``salt-master`` daemon they are connected to, which
``salt-master`` daemon then relays the data back through its ``salt-syndic``
daemon until the data reaches the Master or Syndic node that issued the command.

Syndic wait
===========

``syndic_wait`` is a master configuration file setting that specifies the number of
seconds the Salt client should wait for additional syndics to check in with their
lists of expected minions before giving up. This value defaults to ``5`` seconds.

The ``syndic_wait`` setting is necessary because the higher-level master does not
have a way of knowing which minions are below the syndics. The higher-level master
has its own list of expected minions and the masters below them have their own lists
as well, so the Salt client does not how long to wait for all returns. The
``syndic_wait`` option allows time for all minions to return to the Salt client.

.. note::

    To reduce the amount of time the CLI waits for Minions to respond, install
    a Minion on the Syndic or tune the value of the ``syndic_wait``
    configuration.

While it is possible to run a Syndic without a Minion installed on the same
system, it is recommended, for a faster CLI response time, to do so.  Without a
Minion installed on the Syndic node, the timeout value of ``syndic_wait``
increases significantly - about three-fold. With a Minion installed on the
Syndic, the CLI timeout resides at the value defined in ``syndic_wait``.

.. note::

    If you have a very large infrastructure or many layers of Syndics, you may
    find that the CLI doesn't wait long enough for the Syndics to return their
    events.  If you think this is the case, you can set the
    :conf_master:`syndic_wait` value in the Master configs on the Master or
    Syndic nodes from which commands are executed.  The default value is ``5``,
    and should work for the majority of deployments.

In order for a Master or Syndic node to return information from Minions that
are below their Syndics, the CLI requires a short wait time in order to allow
the Syndics to gather responses from their Minions. This value is defined in
the :conf_master:`syndic_wait` config option and has a default of five seconds.

Syndic config options
=====================

These are the options that can be used to configure a Syndic node.  Note that
other than ``id``, Syndic config options are placed in the Master config on the
Syndic node.

    - :conf_minion:`id`: Syndic id (shared by the ``salt-syndic`` daemon with a
      potential ``salt-minion`` daemon on the same system)
    - :conf_master:`syndic_master`: Master node IP address or hostname
    - :conf_master:`syndic_master_port`: Master node ret_port
    - :conf_master:`syndic_log_file`: path to the logfile (absolute or not)
    - :conf_master:`syndic_pidfile`: path to the pidfile (absolute or not)
    - :conf_master:`syndic_wait`: time in seconds to wait on returns from this syndic

Minion Data Cache
=================

Beginning with Salt 2016.11.0, the :ref:`Pluggable Minion Data Cache <pluggable-data-cache>`
was introduced. The minion data cache contains the Salt Mine data, minion grains, and minion
pillar information cached on the Salt Master. By default, Salt uses the ``localfs`` cache
module, but other external data stores can be used instead.

Using a pluggable minion cache modules allows for the data stored on a Salt Master about
Salt Minions to be replicated on other Salt Masters the Minion is connected to. Please see
the :ref:`Minion Data Cache <cache>` documentation for more information and configuration
examples.
