.. _salt-mine:

=============
The Salt Mine
=============

Granted, it took a while for this name to be used in Salt, but version 0.15.0
introduces a new system to Salt called the Salt Mine.

The Salt Mine is used to bridge the gap between setting static variables and
gathering live data. The Salt mine is used to collect arbitrary data from
minions and store it on the master. This data is then made available to
all minions via the ``mine`` module.

The data is gathered on the minion and sent back to the master where only
the most recent data is maintained (if long term data is required use
returners or the external job cache).

Mine Functions
==============

To enable the Salt Mine the `mine_functions` option needs to be applied to a
minion. This option can be applied via the minion's configuration file, or the
minion's pillar. The `mine_functions` option dictates what functions are being
executed and allows for arguments to be passed in:

.. code-block:: yaml

    mine_functions:
      network.interfaces: []
      test.ping: []

Mine Interval
=============

The Salt Mine functions are executed when the minion starts and at a given
interval by the scheduler. The default interval is every 60 minutes and can
be adjusted for the minion via the `mine_interval` option:

.. code-block:: yaml

    mine_interval: 60
