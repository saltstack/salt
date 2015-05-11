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

The `beacon` Function
---------------------

The beacons system will look for a function named `beacon` in the module. If
this function is not present then the beacon will not be fired. This function is
called on a regular basis and defaults to being called on every iteration of the
minion, which can be tens to hundreds of times a second. This means that the 
`beacon` function cannot block and should not be CPU or IO intensive.

The beacon function will be passed in the configuration for the executed
beacon. This makes it easy to establish a flexible configuration for each
called beacon. This is also the preferred way to ingest the beacon's
configuration as it allows for the configuration to be dynamically updated
while the minion is running by configuring the beacon in the minion's pillar.

The Beacon Return
-----------------

The information returned from the beacon is expected to follow a predefined
structure. The returned value needs to be a list of dictionaries (standard
python dictionaries are preferred, no ordered dicts are needed).

The dictionaries represent individual events to be fired on the minion and
master event buses. Each dict is a single event. The dict can contain any
arbitrary keys but the 'tag' key will be extracted and added to the tag of
the fired event.

The return data structure would look something like this:

.. code-block:: python

    [{'changes': ['/foo/bar'], 'tag': 'foo'},
     {'changes': ['/foo/baz'], 'tag': 'bar'}]

Calling Execution Modules
-------------------------

Execution modules are still the preferred location for all work and system
interaction to happen in Salt. For this reason the `__salt__` variable is
available inside the beacon.

Please be careful when calling functions in `__salt__`, while this is the
preferred means of executing complicated routines in Salt not all of the
execution modules have been written with beacons in mind. Watch out for
execution modules that may be CPU intense or IO bound. Please feel free to
add new execution modules and functions to back specific beacons.
