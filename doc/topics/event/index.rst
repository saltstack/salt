=================
Salt Event System
=================

Salt 0.9.10 introduced the Salt Event System. This system is used to fire
off events enabling third party applications or external processes to react
to behavior within Salt.

The event system is comprised of a few components, the event sockets which
publish events, and the event library which can listen to events and send
events into the salt system.

Listening for Events
====================

The event system is accessed via the event library and can only be accessed
by the same system user that Salt is running as. To listen to events a
SaltEvent object needs to be created and then the get_event function needs to
be run. The SaltEvent object needs to know the location that the Salt Unix
sockets are kept. In the configuration this is the ``sock_dir`` option. The
``sock_dir`` option defaults to "/var/run/salt/master" on most systems.

The following code will check for a single event:

.. code-block:: python

    import salt.utils.event

    event = salt.utils.event.MasterEvent('/var/run/salt/master')

    data = event.get_event()

Events will also use a "tag". A "tag" allows for events to be filtered. By
default all events will be returned, but if only authentication events are
desired, then pass the tag "auth". Also, the get_event method has a default
poll time assigned of 5 seconds, to change this time set the "wait" option.
This example will only listen for auth events and will wait for 10 seconds
instead of the default 5.

.. code-block:: python

    import salt.utils.event

    event = salt.utils.event.MasterEvent('/var/run/salt/master')

    data = event.get_event(wait=10, tag='auth')

Instead of looking for a single event, the iter_events method can be used to
make a generator which will continually yield salt events. The iter_events
method also accepts a tag, but not a wait time:

.. code-block:: python

    import salt.utils.event

    event = salt.utils.event.MasterEvent('/var/run/salt/master')

    for data in event.iter_events(tag='auth'):
        print(data)


Firing Events
=============

It is possible to fire events on either the minion's local bus, or to fire
events intended for the master. To fire a local event from the minion, on the
command line:

.. code-block:: bash

    salt-call event.fire '{"data": "message to be sent in the event"}' 'tag'

To fire an event to be sent to the master, from the minion:

.. code-block:: bash

    salt-call event.fire_master '{"data": "message for the master"}' 'tag'

If a process is listening on the minion, it may be useful for a user on the
master to fire an event to it:

.. code-block:: bash

    salt minionname event.fire '{"data": "message for the minion"}' 'tag'


Firing Events From Code
=======================

Events can be very useful when writing execution modules, in order to inform
various processes on the master when a certain task has taken place. In Salt
versions previous to 0.17.0, the basic code looks like:

.. code-block:: python

    # Import the proper library
    import salt.utils.event
    # Fire deploy action
    sock_dir = '/var/run/salt/minion'
    event = salt.utils.event.SaltEvent('master', sock_dir)
    event.fire_event('Message to be sent', 'tag')

In Salt version 0.17.0, the ability to send a payload with a more complex data
structure than a string was added. When using this interface, a Python
dictionary should be sent instead.

.. code-block:: python

    # Import the proper library
    import salt.utils.event
    # Fire deploy action
    sock_dir = '/var/run/salt/minion'
    payload = {'sample-msg': 'this is a test',
               'example': 'this is the same test'}
    event = salt.utils.event.SaltEvent('master', sock_dir)
    event.fire_event(payload, 'tag')

It should be noted that this code can be used in 3rd party applications as well.
So long as the salt-minion process is running, the minion socket can be used:

.. code-block:: python

    sock_dir = '/var/run/salt/minion'

So long as the salt-master process is running, the master socket can be used:

.. code-block:: python

    sock_dir = '/var/run/salt/master'

This allows 3rd party applications to harness the power of the Salt event bus
programmatically, without having to make other calls to Salt. A 3rd party
process can listen to the event bus on the master, and another 3rd party
process can fire events to the process on the master, which Salt will happily
pass along.

