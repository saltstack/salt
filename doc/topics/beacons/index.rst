.. _beacons:

=======
Beacons
=======

The beacon system allows the minion to hook into system processes and
continually translate external events into the salt event bus. The
primary example of this is the :py:mod:`~salt.beacons.inotify` beacon. This
beacon uses inotify to watch configured files or directories on the minion for
changes, creation, deletion etc.

This allows for the changes to be sent up to the master where the
reactor can respond to changes.

Configuring The Beacons
=======================

The beacon system, like many others in Salt, can be configured via the
minion pillar, grains, or local config file:

.. code-block:: yaml

    beacons:
      inotify:
        /etc/httpd/conf.d: {}
        /opt: {}

Optionally, a beacon can be run on an interval other than the default 
``loop_interval``, which is typically set to 1 second.

To run a beacon every 5 seconds, for example, provide an ``interval`` argument
to a beacon.

.. code-block:: yaml

    beacons:
      inotify:
        /etc/httpd/conf.d: {}
        /opt: {}
        interval: 5
      load:
        - 1m:
          - 0.0
          - 2.0
        - 5m:
          - 0.0
          - 1.5
        - 15m:
          - 0.1
          - 1.0
        - interval: 10


Writing Beacon Plugins
======================

Beacon plugins use the standard Salt loader system, meaning that many of the
constructs from other plugin systems holds true, such as the ``__virtual__``
function.

The important function in the Beacon Plugin is the ``beacon`` function. When
the beacon is configured to run, this function will be executed repeatedly
by the minion. The ``beacon`` function therefore cannot block and should be
as lightweight as possible. The ``beacon`` also must return a list of dicts,
each dict in the list will be translated into an event on the master.

Please see the :py:mod:`~salt.beacons.inotify` beacon as an example.
