.. _beacons:

=======
Beacons
=======

The beacon system allows the minion to hook into a variety of system processes
and continually monitor these processes. When monitored activity occurs in
a system process, an event is sent on the Salt event bus that can
be used to trigger a :ref:`reactor <reactor>`.

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
