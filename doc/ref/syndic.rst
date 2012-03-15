===========
Salt Syndic
===========

The Salt Syndic interface is a powerful tool which allows for the construction
of Salt command topologies. A basic Salt setup has a Salt Master commanding a
group of Salt Minions. The Syndic interface is a special passthrough
minion, it is run on a master and connects to another master, then the master
that the Syndic minion is listening to can control the minions attached to
the master running the syndic.

The intent for supporting many layouts is not presented with the intent of
supposing the use of any single topology, but to allow a more flexible method
of controlling many systems.

Configuring the Syndic
======================

Since the Syndic only needs to be attached to a higher level master the
configuration is very simple. On a master that is running a syndic to connect
to a higher level master the syndic_master option needs to be set in the
master config file. The syndic_master option contains the hostname or ip
address of the master server that can control the master that the syndic is
running on.

The master that the syndic connects to sees the syndic as an ordinary minion,
and treats it as such. the higher level master will need to accept the syndic's
minion key like any other minion. This master will also need to set the
order_masters value in the configuration to True. The order_masters option in
the config on the higher level master is very important, to control a syndic
extra information needs to be sent with the publications, the order_masters
option makes sure that the extra data is sent out.

Running the Syndic
==================

The Syndic is a separate daemon that needs to be started on the master that is
controlled by a higher master. Starting the Syndic daemon is the same as
starting the other Salt daemons.

.. code-block:: bash

    # salt-syndic
