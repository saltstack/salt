.. _beacons:

=======
Beacons
=======

Beacons let you use the Salt event system to monitor non-Salt processes. The
beacon system allows the minion to hook into a variety of system processes and
continually monitor these processes. When monitored activity occurs in a system
process, an event is sent on the Salt event bus that can be used to trigger
a :ref:`reactor <reactor>`.

Salt beacons can currently monitor and send Salt events for many system
activities, including:

- file system changes
- system load
- service status
- shell activity, such as user login
- network and disk usage

See :ref:`beacon modules <all-salt.beacons>` for a current list.

.. note::
    Salt beacons are an event generation mechanism. Beacons leverage the Salt
    :ref:`reactor <reactor>` system to make changes when beacon events occur.


Configuring Beacons
===================

Salt beacons do not require any changes to the system process that
is being monitored, everything is configured using Salt.

Beacons are typically enabled by placing a ``beacons:`` top level block in the
minion configuration file:

.. code-block:: yaml

    beacons:
      inotify:
        /etc/httpd/conf.d: {}
        /opt: {}

The beacon system, like many others in Salt, can also be configured via the
minion pillar, grains, or local config file.

Beacon Monitoring Interval
--------------------------

Beacons monitor on a 1-second interval by default. To set a different interval,
provide an ``interval`` argument to a beacon. The following beacons run on
5- and 10-second intervals:

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

Avoiding Event Loops
--------------------

It is important to carefully consider the possibility of creating a loop
between a reactor and a beacon. For example, one might set up a beacon
which monitors whether a file is read which in turn fires a reactor to
run a state which in turn reads the file and re-fires the beacon.

To avoid these types of scenarios, the ``disable_during_state_run``
argument may be set. If a state run is in progress, the beacon will
not be run on its regular interval until the minion detects that the
state run has completed, at which point the normal beacon interval
will resume.

.. code-block:: yaml

    beacons:
      inotify:
        /etc/passwd: {}
        disable_during_state_run: True


Beacon Example
==============

This example demonstrates configuring the :py:mod:`~salt.beacons.inotify`
beacon to monitor a file for changes, and then create a backup each time
a change is detected.

.. note::
    The inotify beacon requires Pyinotify on the minion, install it using
    ``salt myminion pkg.install python-inotify``.

First, on the Salt minion, add the following beacon configuration to
``/ect/salt/minion``:

.. code-block:: yaml

   beacons:
     inotify:
       home/user/importantfile:
         mask:
           - modify

Replace ``user`` in the previous example with the name of your user account,
and then save the configuration file and restart the minion service.

Next, create a file in your home directory named ``importantfile`` and add some
simple content. The beacon is now set up to monitor this file for
modifications.

View Events on the Master
-------------------------

On your Salt master, start the event runner using the following command:

.. code-block:: bash

   salt-run state.event pretty=true

This runner displays events as they are received on the Salt event bus. To test
the beacon you set up in the previous section, make and save
a modification to the ``importantfile`` you created. You'll see an event
similar to the following on the event bus:

.. code-block:: json

   salt/beacon/minion1/inotify/home/user/importantfile	{
    "_stamp": "2015-09-09T15:59:37.972753",
    "data": {
        "change": "IN_IGNORED",
        "id": "minion1",
        "path": "/home/user/importantfile"
    },
    "tag": "salt/beacon/minion1/inotify/home/user/importantfile"
   }


This indicates that the event is being captured and sent correctly. Now you can
create a reactor to take action when this event occurs.

Create a Reactor
----------------

On your Salt master, create a file named ``srv/reactor/backup.sls``. If the
``reactor`` directory doesn't exist, create it. Add the following to ``backup.sls``:

.. code-block:: yaml

   backup file:
    cmd.file.copy:
      - tgt: {{ data['data']['id'] }}
      - arg:
        - {{ data['data']['path'] }}
        - {{ data['data']['path'] }}.bak

Next, add the code to trigger the reactor to ``ect/salt/master``:

.. code-block:: yaml

   reactor:
     - salt/beacon/*/inotify/*/importantfile:
       - /srv/reactor/backup.sls


This reactor creates a backup each time a file named ``importantfile`` is
modified on a minion that has the :py:mod:`~salt.beacons.inotify` beacon
configured as previously shown.

.. note::
    You can have only one top level ``reactor`` section, so if one already
    exists, add this code to the existing section. See :ref:`Understanding
    the Structure of Reactor Formulas <reactor-structure>` to learn more about
    reactor SLS syntax.


Start the Salt Master in Debug Mode
-----------------------------------

To help with troubleshooting, start the Salt master in debug mode:

.. code-block:: yaml

   service salt-master stop
   salt-master -l debug

When debug logging is enabled, event and reactor data are displayed so you can
discover syntax and other issues.

Trigger the Reactor
-------------------

On your minion, make and save another change to ``importantfile``. On the Salt
master, you'll see debug messages that indicate the event was received and the
``file.copy`` job was sent. When you list the directory on the minion, you'll now
see ``importantfile.bak``.

All beacons are configured using a similar process of enabling the beacon,
writing a reactor SLS, and mapping a beacon event to the reactor SLS.

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

Distributing Custom Beacons
---------------------------

Custom beacons can be distributed to minions using ``saltutil``, see
:ref:`Dynamic Module Distribution <dynamic-module-distribution>`.

